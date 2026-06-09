"""
智能学习助手 — 学习进度诊断引擎
负责: RAG + FULL
任务: TASK-DIAG-001

基于 MySQL knowledge_diagnosis 表，实现知识点薄弱项检测。
当学生对同一知识点连续提问超过阈值时，生成个性化诊断建议。
"""

import json

from src.database.db_manager import DBManager
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.diagnosis")

# 触发诊断的提问次数阈值
DIAGNOSIS_THRESHOLD = 3

# 知识点提取 Prompt
EXTRACT_TOPIC_PROMPT = """请从以下学生问题中提取涉及的核心知识点名称。
只输出知识点名称，不要其他内容。如果有多个知识点，只输出最核心的一个。

示例:
问题: "C语言中指针和数组有什么区别？"
知识点: 指针与数组

问题: "什么是面向对象的封装？"
知识点: 面向对象封装

问题: "{question}"
知识点:"""

# 诊断建议生成 Prompt
DIAGNOSIS_PROMPT = """你是一个学习诊断专家。学生在"{topic}"相关问题上已经连续提问了 {count} 次。

这意味着学生可能在这个知识点上存在理解困难。

请生成一段简短的诊断建议（100字以内），包括：
1. 学生可能存在的困惑点
2. 建议的复习方向

诊断建议:"""


class DiagnosisEngine:
    """
    学习进度诊断引擎

    功能:
    1. 从用户问题中提取知识点关键词
    2. 统计同一会话中对同一知识点的提问次数
    3. 超过阈值时生成个性化诊断建议
    4. 返回薄弱知识点列表供前端展示
    """

    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()
        self._llm_client = LLMClient()
        logger.info("DiagnosisEngine 初始化完成")

    def extract_topic(self, question: str) -> str:
        """
        用 LLM 从问题中提取核心知识点

        Args:
            question: 用户问题

        Returns:
            知识点名称字符串
        """
        try:
            topic = self._llm_client.chat(
                messages=[{"role": "user", "content": EXTRACT_TOPIC_PROMPT.format(question=question)}],
                temperature=0.1,
                max_tokens=50,
            )
            topic = topic.strip().strip('"').strip("'").strip("知识点:").strip("知识点：")
            # 限制长度
            if len(topic) > 100:
                topic = topic[:100]
            return topic if topic else "其他"
        except Exception as e:
            logger.warning("知识点提取失败: %s", str(e))
            return "其他"

    def record_question(self, session_id: str, question: str) -> dict:
        """
        记录一次提问并检查是否需要触发诊断

        Args:
            session_id: 会话 ID
            question: 用户问题

        Returns:
            {
                "topic": str,               # 提取的知识点
                "count": int,               # 该知识点累计提问次数
                "triggered": bool,          # 是否触发了诊断
                "suggestion": str | None    # 诊断建议（触发时才有）
            }
        """
        topic = self.extract_topic(question)
        logger.info("知识点提取: '%s' → '%s'", question[:50], topic)

        # 查询当前计数
        sql = """
            SELECT question_count, suggestion
            FROM knowledge_diagnosis
            WHERE session_id = %s AND topic = %s
        """
        existing = self.db.fetch_one(sql, (session_id, topic))

        if existing:
            new_count = existing["question_count"] + 1
            sql = """
                UPDATE knowledge_diagnosis
                SET question_count = %s, last_asked_at = NOW()
                WHERE session_id = %s AND topic = %s
            """
            self.db.execute(sql, (new_count, session_id, topic))
        else:
            new_count = 1
            sql = """
                INSERT INTO knowledge_diagnosis (session_id, topic, question_count)
                VALUES (%s, %s, 1)
            """
            self.db.execute(sql, (session_id, topic))

        # 检查是否触发诊断
        triggered = new_count >= DIAGNOSIS_THRESHOLD
        suggestion = None

        if triggered and (not existing or not existing.get("suggestion")):
            suggestion = self._generate_suggestion(topic, new_count)
            # 存储建议
            sql = """
                UPDATE knowledge_diagnosis
                SET suggestion = %s
                WHERE session_id = %s AND topic = %s
            """
            self.db.execute(sql, (suggestion, session_id, topic))
            logger.info("诊断触发: session=%s topic='%s' count=%d", session_id, topic, new_count)
        elif triggered and existing and existing.get("suggestion"):
            suggestion = existing["suggestion"]

        return {
            "topic": topic,
            "count": new_count,
            "triggered": triggered,
            "suggestion": suggestion,
        }

    def get_weak_topics(self, session_id: str) -> list:
        """
        获取会话中的薄弱知识点列表

        Returns:
            [
                {
                    "topic": str,
                    "question_count": int,
                    "suggestion": str,
                    "last_asked_at": str
                }
            ]
        """
        sql = """
            SELECT topic, question_count, suggestion, last_asked_at
            FROM knowledge_diagnosis
            WHERE session_id = %s AND question_count >= %s
            ORDER BY question_count DESC
        """
        results = self.db.fetch_all(sql, (session_id, DIAGNOSIS_THRESHOLD))
        from datetime import datetime
        for r in results:
            if isinstance(r.get("last_asked_at"), datetime):
                r["last_asked_at"] = r["last_asked_at"].isoformat()
        return results

    def _generate_suggestion(self, topic: str, count: int) -> str:
        """生成个性化诊断建议"""
        try:
            suggestion = self._llm_client.chat(
                messages=[{"role": "user", "content": DIAGNOSIS_PROMPT.format(
                    topic=topic, count=count
                )}],
                temperature=0.3,
                max_tokens=200,
            )
            return suggestion.strip()
        except Exception as e:
            logger.warning("诊断建议生成失败: %s", str(e))
            return f"你在「{topic}」上已提问 {count} 次，建议系统复习该知识点的相关内容。"

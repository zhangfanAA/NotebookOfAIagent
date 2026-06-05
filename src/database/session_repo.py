"""
智能学习助手 — 会话与消息持久化模块
负责: FULL
任务: TASK-DATA-006

基于 MySQL 实现会话管理和消息存储。
"""

from datetime import datetime

from src.database.db_manager import DBManager
from src.logger import get_logger
from src.utils.helpers import generate_id

logger = get_logger("database.session_repo")


class SessionRepository:
    """会话 CRUD 操作"""

    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def create_session(self, title: str = "新会话") -> str:
        """
        创建新会话

        Args:
            title: 会话标题

        Returns:
            session_id (UUID 格式)
        """
        session_id = generate_id()
        sql = "INSERT INTO sessions (session_id, title) VALUES (%s, %s)"
        self.db.execute(sql, (session_id, title))
        logger.info("创建新会话: %s (%s)", session_id, title)
        return session_id

    def get_sessions(self, limit: int = 50) -> list:
        """
        获取会话列表（按更新时间倒序）

        Returns:
            [{"session_id": str, "title": str, "created_at": str, "updated_at": str}]
        """
        sql = """
            SELECT session_id, title, created_at, updated_at
            FROM sessions
            WHERE is_active = 1
            ORDER BY updated_at DESC
            LIMIT %s
        """
        results = self.db.fetch_all(sql, (limit,))
        # datetime 转字符串
        for r in results:
            for key in ("created_at", "updated_at"):
                if isinstance(r.get(key), datetime):
                    r[key] = r[key].isoformat()
        return results

    def search_sessions(self, keyword: str, limit: int = 20) -> list:
        """按关键词搜索会话（标题 + 消息内容）"""
        sql = """
            SELECT DISTINCT s.session_id, s.title, s.created_at, s.updated_at
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.is_active = 1
              AND (s.title LIKE %s OR m.content LIKE %s)
            ORDER BY s.updated_at DESC
            LIMIT %s
        """
        pattern = f"%{keyword}%"
        results = self.db.fetch_all(sql, (pattern, pattern, limit))
        for r in results:
            for key in ("created_at", "updated_at"):
                if isinstance(r.get(key), datetime):
                    r[key] = r[key].isoformat()
        return results

    def get_session(self, session_id: str) -> dict:
        """获取单个会话信息"""
        sql = "SELECT * FROM sessions WHERE session_id = %s AND is_active = 1"
        result = self.db.fetch_one(sql, (session_id,))
        if result:
            for key in ("created_at", "updated_at"):
                if isinstance(result.get(key), datetime):
                    result[key] = result[key].isoformat()
        return result

    def update_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        sql = "UPDATE sessions SET title = %s WHERE session_id = %s"
        affected = self.db.execute(sql, (title, session_id))
        return affected > 0

    def delete_session(self, session_id: str) -> bool:
        """软删除会话（设置 is_active=0）"""
        sql = "UPDATE sessions SET is_active = 0 WHERE session_id = %s"
        affected = self.db.execute(sql, (session_id,))
        logger.info("删除会话: %s (affected=%d)", session_id, affected)
        return affected > 0

    def update_notes(self, session_id: str, notes: str) -> bool:
        """更新会话笔记"""
        sql = "UPDATE sessions SET notes = %s WHERE session_id = %s"
        affected = self.db.execute(sql, (notes, session_id))
        return affected > 0

    def get_notes(self, session_id: str) -> str:
        """获取会话笔记"""
        sql = "SELECT notes FROM sessions WHERE session_id = %s"
        result = self.db.fetch_one(sql, (session_id,))
        return result.get("notes", "") if result else ""

    def add_favorite(self, session_id: str, content: str, question: str = None, message_id: int = None) -> int:
        """添加收藏"""
        sql = """
            INSERT INTO favorites (session_id, message_id, content, question)
            VALUES (%s, %s, %s, %s)
        """
        return self.db.execute_returning_id(sql, (session_id, message_id, content, question))

    def remove_favorite(self, favorite_id: int) -> bool:
        """取消收藏"""
        sql = "DELETE FROM favorites WHERE id = %s"
        affected = self.db.execute(sql, (favorite_id,))
        return affected > 0

    def get_favorites(self, session_id: str, limit: int = 20) -> list:
        """获取收藏列表"""
        sql = """
            SELECT id, session_id, content, question, created_at
            FROM favorites
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        results = self.db.fetch_all(sql, (session_id, limit))
        for r in results:
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
        return results

    def is_favorited(self, session_id: str, content: str) -> bool:
        """检查是否已收藏"""
        sql = "SELECT COUNT(*) AS cnt FROM favorites WHERE session_id = %s AND content = %s"
        result = self.db.fetch_one(sql, (session_id, content))
        return result.get("cnt", 0) > 0 if result else False


class MessageRepository:
    """消息 CRUD 操作"""

    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list = None,
        reasoning: str = None,
        confidence: float = None,
        loop_count: int = 0,
    ) -> int:
        """
        存储一条消息

        Args:
            session_id: 会话ID
            role: "user" / "assistant" / "system"
            content: 消息内容
            sources: 引用来源列表（仅 assistant 消息）
            reasoning: 推理过程（仅 assistant 消息）
            confidence: 置信度（仅 assistant 消息）
            loop_count: 循环次数（仅 assistant 消息）

        Returns:
            新消息的自增 ID
        """
        import json

        sources_json = json.dumps(sources, ensure_ascii=False) if sources else None

        sql = """
            INSERT INTO messages
            (session_id, role, content, sources, reasoning, confidence, loop_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        msg_id = self.db.execute_returning_id(
            sql, (session_id, role, content, sources_json, reasoning, confidence, loop_count)
        )
        logger.debug("存储消息: session=%s role=%s len=%d", session_id, role, len(content))
        return msg_id

    def get_messages(self, session_id: str, limit: int = 100) -> list:
        """
        获取会话的全部消息

        Returns:
            [{"id": int, "role": str, "content": str, "sources": list,
              "reasoning": str, "confidence": float, "created_at": str}]
        """
        import json

        sql = """
            SELECT id, role, content, sources, reasoning, confidence, loop_count, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        results = self.db.fetch_all(sql, (session_id, limit))
        for r in results:
            # 解析 sources JSON
            if r.get("sources") and isinstance(r["sources"], str):
                try:
                    r["sources"] = json.loads(r["sources"])
                except json.JSONDecodeError:
                    r["sources"] = []
            # datetime 转字符串
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
        return results

    def get_recent_context(self, session_id: str, turns: int = 5) -> list:
        """
        获取最近 N 轮对话，用于构建 LLM 上下文

        Args:
            session_id: 会话ID
            turns: 获取最近几轮（1轮 = 1 user + 1 assistant）

        Returns:
            [{"role": "user"|"assistant", "content": str}]
        """
        limit = turns * 2
        sql = """
            SELECT role, content
            FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE session_id = %s AND role IN ('user', 'assistant')
                ORDER BY created_at DESC
                LIMIT %s
            ) AS sub
            ORDER BY created_at ASC
        """
        results = self.db.fetch_all(sql, (session_id, limit))
        return [{"role": r["role"], "content": r["content"]} for r in results]

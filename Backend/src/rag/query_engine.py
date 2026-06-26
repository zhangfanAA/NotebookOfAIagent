"""
RAG 查询引擎模块
负责: RAG

封装查询核心逻辑（检索+生成）、多轮上下文增强。
"""

import re

from src.rag.llm_client import LLMClient
from src.rag.diagnosis import DiagnosisEngine
from src.rag import chat_history_store
from src.utils.security import sanitize_input, build_safe_system_prompt
from src.config import get_config
from src.logger import get_logger

logger = get_logger("rag.query_engine")


def _generate_title(llm_client, question: str) -> str:
    """用 LLM 根据问题生成简短标题，失败时降级为截断"""
    prompt = f"用中文起一个简短标题，不超过15字，直接输出标题：{question[:200]}"
    try:
        title = llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        title = title.strip().strip('"').strip("'").replace("\n", "").replace("。", "")
        if len(title) > 20:
            title = title[:20]
        if title:
            return title
    except Exception as e:
        logger.debug("LLM 生成标题失败: %s", e)
    return question.strip()[:20]


class QueryEngine:
    """查询引擎"""

    def __init__(self, session_manager):
        self._config = get_config()
        self._session_mgr = session_manager
        self._llm_client = LLMClient()
        self._diagnosis = DiagnosisEngine()
        self._safe_system_prompt = build_safe_system_prompt()

    def query(self, question: str, session_id: str, llm_client=None, user_id=None, memory_mode=False) -> dict:
        """
        核心查询接口（含安全校验 + 多轮上下文增强）

        Args:
            question: 用户输入的问题（不能为空）
            session_id: 会话标识

        Returns:
            成功: {"answer": str, "sources": list, ...}
            失败: {"error": str, "code": str}
        """
        if not question or not question.strip():
            return {"error": "问题不能为空", "code": "EMPTY_QUESTION"}

        # 安全校验
        safety = sanitize_input(question)
        if not safety["safe"]:
            logger.warning("安全校验失败: session=%s input='%s'", session_id, question[:80])
            return {
                "error": safety["warning"],
                "code": "SECURITY_VIOLATION",
                "answer": "抱歉，您的提问包含不安全的内容。请使用正常的学习问题提问。",
                "sources": [],
                "reasoning": "输入安全校验未通过",
                "confidence": 0.0,
                "loop_count": 0,
            }

        question = safety["text"]
        if safety["warning"]:
            logger.info("输入警告: %s", safety["warning"])

        try:
            # 获取多轮对话上下文
            context_messages = self._session_mgr.get_recent_context(session_id, turns=3)
            effective_question = question
            if context_messages and _has_reference(question):
                effective_question = _rewrite_with_context(question, context_messages)
                logger.info("多轮上下文改写: '%s' → '%s'", question[:50], effective_question[:50])

            # 构建记忆上下文（仅当前会话最近 2 轮，不跨会话检索）
            history_context = ""
            try:
                parts = []
                recent_qa = self._session_mgr.get_recent_context(session_id, turns=2)
                if recent_qa:
                    session_parts = []
                    for m in recent_qa:
                        role = "学生" if m["role"] == "user" else "助手"
                        session_parts.append(f"{role}: {m['content'][:300]}")
                    parts.append(f"[当前会话最近对话]\n" + "\n".join(session_parts))

                if parts:
                    history_context = "\n---\n".join(parts)
            except Exception as e:
                logger.debug("历史记录检索跳过: %s", str(e))

            # 记忆模式：检索当前会话的历史向量
            if memory_mode:
                try:
                    memory_results = chat_history_store.search_history(
                        query=question,
                        top_k=3,
                        session_id=session_id,
                        user_id=user_id,
                    )
                    if memory_results:
                        memory_parts = []
                        for r in memory_results:
                            memory_parts.append(f"Q: {r['question'][:200]}\nA: {r['answer'][:200]}")
                        if not parts:
                            parts = []
                        parts.append(f"[记忆模式 - 相关历史问答]\n" + "\n---\n".join(memory_parts))
                        history_context = "\n---\n".join(parts)
                except Exception as e:
                    logger.debug("记忆模式向量检索跳过: %s", str(e))

            # 构建初始状态
            max_loops = self._config["agent"]["max_loops"]
            query_for_agent = effective_question
            if history_context:
                query_for_agent = f"[相关历史参考]\n{history_context}\n\n[当前问题]\n{effective_question}"

            # 如果传入了用户级 LLMClient，临时替换
            original_llm = self._llm_client
            if llm_client:
                self._llm_client = llm_client

            initial_state: dict = {
                "question": query_for_agent,
                "rewritten_query": None,
                "documents": None,
                "relevance": None,
                "answer": None,
                "sources": None,
                "reasoning": None,
                "confidence": None,
                "messages": [],
                "loop_count": 0,
                "max_loops": max_loops,
                "session_id": session_id,
                "user_id": user_id,
                "llm_client": llm_client,
            }

            # 存储用户消息
            self._session_mgr.add_message(session_id, "user", question)

            # 执行 LangGraph Agent
            from src.rag.graph import get_graph
            graph = get_graph()
            result = graph.invoke(initial_state)

            # 恢复原始 LLMClient
            if llm_client:
                self._llm_client = original_llm

            answer = result.get("answer", "抱歉，无法生成回答")
            sources = result.get("sources", [])
            reasoning = result.get("reasoning", "")
            confidence = result.get("confidence", 0.0)
            loop_count = result.get("loop_count", 0)

            # 存储助手消息
            self._session_mgr.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources=sources,
                reasoning=reasoning,
                confidence=confidence,
                loop_count=loop_count,
            )

            # 存储到聊天记录向量库（增强记忆）
            try:
                chat_history_store.store_qa(session_id, question, answer, sources, user_id=user_id)
            except Exception as e:
                logger.debug("聊天记录存储跳过: %s", str(e))

            # 自动更新会话标题
            self._maybe_update_title(session_id, question)

            # 学习进度诊断
            diagnosis_result = self._diagnosis.record_question(session_id, question)

            logger.info(
                "查询完成: session=%s confidence=%.2f loops=%d diagnosis=%s",
                session_id, confidence, loop_count,
                "触发" if diagnosis_result.get("triggered") else "未触发",
            )

            # 用量信息
            usage_info = self._llm_client.last_usage

            return {
                "answer": answer,
                "sources": sources,
                "reasoning": reasoning,
                "confidence": confidence,
                "loop_count": loop_count,
                "diagnosis": diagnosis_result,
                "usage": usage_info,
            }

        except Exception as e:
            logger.error("查询失败: session=%s error=%s", session_id, str(e))
            return {"error": str(e), "code": "AGENT_ERROR"}

    def query_stream(self, question: str, session_id: str, llm_client=None, user_id=None, memory_mode=False):
        """
        流式查询接口（生成器）

        Yields:
            dict: {"type": "token"|"result"|"error", "data": ...}
        """
        logger.info("query_stream v2 loaded - no self._rewrite_with_context")
        if not question or not question.strip():
            yield {"type": "error", "data": "问题不能为空"}
            return

        safety = sanitize_input(question)
        if not safety["safe"]:
            yield {"type": "error", "data": safety["warning"]}
            return

        question = safety["text"]

        original_llm = None
        try:
            context_messages = self._session_mgr.get_recent_context(session_id, turns=3)
            effective_question = question
            context_used = False
            original_question = None
            if context_messages and _has_reference(question):
                original_question = question
                effective_question = _rewrite_with_context(question, context_messages)
                context_used = True

            # 构建记忆上下文（仅当前会话最近 2 轮，不跨会话检索）
            history_context = ""
            try:
                parts = []
                recent_qa = self._session_mgr.get_recent_context(session_id, turns=2)
                if recent_qa:
                    session_parts = []
                    for m in recent_qa:
                        role = "学生" if m["role"] == "user" else "助手"
                        session_parts.append(f"{role}: {m['content'][:300]}")
                    parts.append(f"[当前会话最近对话]\n" + "\n".join(session_parts))

                if parts:
                    history_context = "\n---\n".join(parts)
            except Exception as e:
                logger.debug("历史记录检索跳过: %s", str(e))

            # 记忆模式：检索当前会话的历史向量
            if memory_mode:
                try:
                    memory_results = chat_history_store.search_history(
                        query=question,
                        top_k=3,
                        session_id=session_id,
                        user_id=user_id,
                    )
                    if memory_results:
                        memory_parts = []
                        for r in memory_results:
                            memory_parts.append(f"Q: {r['question'][:200]}\nA: {r['answer'][:200]}")
                        if not parts:
                            parts = []
                        parts.append(f"[记忆模式 - 相关历史问答]\n" + "\n---\n".join(memory_parts))
                        history_context = "\n---\n".join(parts)
                except Exception as e:
                    logger.debug("记忆模式向量检索跳过: %s", str(e))

            # 执行 Agent 检索+评估
            max_loops = self._config["agent"]["max_loops"]
            query_for_agent = effective_question
            if history_context:
                query_for_agent = f"[相关历史参考]\n{history_context}\n\n[当前问题]\n{effective_question}"
            # 如果传入了用户级 LLMClient，临时替换
            original_llm = self._llm_client
            if llm_client:
                self._llm_client = llm_client

            initial_state: dict = {
                "question": query_for_agent,
                "rewritten_query": None,
                "documents": None,
                "relevance": None,
                "answer": None,
                "sources": None,
                "reasoning": None,
                "confidence": None,
                "messages": [],
                "loop_count": 0,
                "max_loops": max_loops,
                "session_id": session_id,
                "user_id": user_id,
                "llm_client": llm_client,
            }

            self._session_mgr.add_message(session_id, "user", question)

            # 手动执行检索-评估-重写循环
            from src.rag.retrieve import retrieve_node
            from src.rag.grade import grade_node
            from src.rag.rewrite import rewrite_node

            state = dict(initial_state)
            for _ in range(max_loops + 1):
                retrieve_result = retrieve_node(state)
                state.update(retrieve_result)

                grade_result = grade_node(state)
                state.update(grade_result)

                if state.get("relevance") == "yes":
                    break
                if state.get("loop_count", 0) >= max_loops:
                    break

                rewrite_result = rewrite_node(state)
                state.update(rewrite_result)

            # 构建上下文和来源
            documents = state.get("documents", [])
            sources_list = []
            context_parts = []

            if state.get("relevance") == "yes" and documents:
                seen_sources = set()
                for i, doc in enumerate(documents):
                    source_name = doc.get("metadata", {}).get("source", "未知来源")
                    page = doc.get("metadata", {}).get("page", "?")
                    score = doc.get("score", 0)
                    # 去重：同一来源+页码+内容前100字只保留最高分
                    dedup_key = (source_name, page, doc["content"][:100])
                    if dedup_key in seen_sources:
                        continue
                    seen_sources.add(dedup_key)
                    context_parts.append(f"【参考资料 {i+1}】来源:《{source_name}》第{page}页\n{doc['content']}")
                    sources_list.append({
                        "content": doc["content"][:200],
                        "source": source_name,
                        "page": page,
                        "score": score,
                    })

            from src.rag.generate import GENERATE_PROMPT, FALLBACK_PROMPT
            if state.get("relevance") == "yes" and documents:
                prompt = GENERATE_PROMPT.format(
                    context="\n\n---\n\n".join(context_parts),
                    question=question,
                )
                llm_messages = [
                    {"role": "system", "content": build_safe_system_prompt()},
                    {"role": "user", "content": prompt},
                ]
            else:
                prompt = FALLBACK_PROMPT.format(question=question)
                llm_messages = [{"role": "user", "content": prompt}]

            # 流式输出
            full_answer = ""
            for token in self._llm_client.chat_stream(llm_messages, temperature=0.3):
                full_answer += token
                yield {"type": "token", "data": token}

            # 计算置信度和统计
            avg_score = sum(s["score"] for s in sources_list) / len(sources_list) if sources_list else 0
            confidence = min(1.0, avg_score * 1.2)
            loop_count = state.get("loop_count", 0)
            reasoning = f"基于 {len(documents)} 个文档，循环 {loop_count} 次"

            # 存储助手消息
            self._session_mgr.add_message(
                session_id=session_id,
                role="assistant",
                content=full_answer,
                sources=sources_list,
                reasoning=reasoning,
                confidence=round(confidence, 2),
                loop_count=loop_count,
            )

            # 存储到聊天记录向量库（增强记忆）
            try:
                chat_history_store.store_qa(session_id, question, full_answer, sources_list, user_id=user_id)
            except Exception as e:
                logger.debug("聊天记录存储跳过: %s", str(e))

            new_title = self._maybe_update_title(session_id, question)
            diagnosis_result = self._diagnosis.record_question(session_id, question)

            # 用量信息
            usage_info = self._llm_client.last_usage

            # 发送标题更新事件
            if new_title:
                yield {"type": "title", "data": new_title}

            yield {
                "type": "result",
                "data": {
                    "sources": sources_list,
                    "reasoning": reasoning,
                    "confidence": round(confidence, 2),
                    "loop_count": loop_count,
                    "diagnosis": diagnosis_result,
                    "context_used": context_used,
                    "original_question": original_question,
                    "rewritten_question": effective_question if context_used else None,
                    "usage": usage_info,
                },
            }

        except Exception as e:
            logger.error("流式查询失败: session=%s error=%s", session_id, str(e))
            yield {"type": "error", "data": str(e)}
        finally:
            # 恢复原始 LLMClient
            if llm_client and original_llm is not None:
                self._llm_client = original_llm

    def _maybe_update_title(self, session_id: str, question: str) -> str | None:
        """第一条消息时自动生成会话标题，返回新标题或 None"""
        try:
            from src.database.session_repo import SessionRepository
            session_repo = SessionRepository()
            session = session_repo.get_session(session_id)
            if not session:
                return None
            current_title = session.get("title", "")
            if current_title not in ("新会话", "New Session", "", None):
                return None
            logger.info("自动生成会话标题: session=%s question='%s'", session_id, question[:50])
            title = _generate_title(self._llm_client, question)
            if title:
                session_repo.update_title(session_id, title)
                logger.info("会话标题已更新: %s -> %s", session_id, title)
                return title
            return None
        except Exception as e:
            logger.debug("更新会话标题失败: %s", str(e))

    def get_weak_topics(self, session_id: str) -> list:
        """获取薄弱知识点列表"""
        return self._diagnosis.get_weak_topics(session_id)

    def get_conversation_summary(self, session_id: str) -> dict:
        """生成对话摘要"""
        messages = self._session_mgr.get_messages(session_id)
        if not messages:
            return {"summary": "暂无对话记录", "topics": [], "message_count": 0}

        conversation = "\n".join(
            f"{'学生' if m['role'] == 'user' else '助手'}: {m['content'][:300]}"
            for m in messages if m["role"] in ("user", "assistant")
        )

        prompt = f"""请分析以下对话，生成：
1. 一段简短的对话摘要（50字以内）
2. 涉及的主要话题列表（最多5个）

对话内容:
{conversation}

请用以下格式输出:
摘要: [摘要内容]
话题: [话题1], [话题2], ..."""

        try:
            response = self._llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )

            summary = ""
            topics = []
            for line in response.split("\n"):
                if line.startswith("摘要:"):
                    summary = line.replace("摘要:", "").strip()
                elif line.startswith("话题:"):
                    topics = [t.strip() for t in line.replace("话题:", "").split(",")]

            return {
                "summary": summary or "对话内容总结",
                "topics": topics,
                "message_count": len(messages),
            }
        except Exception as e:
            logger.warning("对话摘要生成失败: %s", str(e))
            return {
                "summary": f"共 {len(messages)} 条消息",
                "topics": [],
                "message_count": len(messages),
            }

    def get_recent_topics(self, session_id: str) -> list:
        """获取最近提问的话题"""
        from src.database.session_repo import SessionRepository
        session_repo = SessionRepository()
        sql = """
            SELECT topic, question_count AS count
            FROM knowledge_diagnosis
            WHERE session_id = %s
            ORDER BY last_asked_at DESC
            LIMIT 5
        """
        return session_repo.db.fetch_all(sql, (session_id,))

    def get_learning_progress(self, session_id: str) -> dict:
        """获取学习进度数据"""
        messages = self._session_mgr.get_messages(session_id)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]

        confidences = [m.get("confidence", 0) for m in assistant_msgs if m.get("confidence") is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        weak_topics = self._diagnosis.get_weak_topics(session_id)

        knowledge_gaps = []
        for topic in weak_topics:
            if topic.get("question_count", 0) >= 3:
                knowledge_gaps.append({
                    "topic": topic["topic"],
                    "question_count": topic["question_count"],
                    "suggestion": topic.get("suggestion", "建议复习该知识点"),
                })

        strong_topics = [
            m.get("sources", [{}])[0].get("source", "")
            for m in assistant_msgs
            if m.get("confidence", 0) > 0.7 and m.get("sources")
        ]
        strong_topics = list(set(strong_topics))[:5]

        return {
            "total_questions": len(user_msgs),
            "total_answers": len(assistant_msgs),
            "avg_confidence": round(avg_confidence, 2),
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "knowledge_gaps": knowledge_gaps,
        }


def _has_reference(question: str) -> bool:
    """检测问题是否包含指代词"""
    reference_patterns = [
        r"它", r"这个", r"那个", r"这些", r"那些",
        r"上面", r"下面", r"前面", r"后面",
        r"刚才", r"之前", r"上述",
        r"第[一二三四五六七八九十]个",
        r"第\d+个",
        r"\bit\b", r"\bthis\b", r"\bthat\b",
        r"\bthese\b", r"\bthose\b",
        r"\babove\b", r"\bbelow\b",
        r"\bmentioned\b", r"\breferred\b",
    ]
    for pattern in reference_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return True
    return False


def _rewrite_with_context(question: str, context_messages: list) -> str:
    """结合上下文改写问题"""
    context_text = "\n".join(
        f"{'学生' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
        for m in context_messages
    )

    prompt = f"""请根据对话历史，将学生最新的问题改写为一个独立完整的、不依赖上下文就能理解的问题。
只输出改写后的问题，不要添加任何解释。

对话历史:
{context_text}

学生最新问题: {question}

改写后的独立问题:"""

    try:
        llm = LLMClient()
        rewritten = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        return rewritten.strip() if rewritten.strip() else question
    except Exception as e:
        logger.warning("上下文改写失败: %s", str(e))
        return question

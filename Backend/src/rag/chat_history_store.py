"""
聊天记录向量存储模块（按用户隔离版）
负责: RAG

将聊天问答对存入按用户隔离的 Chroma 集合:
- 知识库文档: docs_{user_id}  （vector_store.py）
- 聊天记录:   chat_{user_id}  （本模块）

同一个用户的不同会话通过 session_id 元数据区分。
不同用户之间数据完全隔离，互不干扰。
"""

import hashlib
import time

from src.data.vector_store import get_chroma_client, embed_texts, embed_query
from src.logger import get_logger

logger = get_logger("rag.chat_history_store")

# 旧版共享集合名（迁移清理用）
_LEGACY_COLLECTION_NAME = "chat_history"


def _collection_name(user_id: int) -> str:
    """按用户生成集合名: chat_{user_id}"""
    return f"chat_{user_id}"


def _get_collection(user_id: int):
    """获取指定用户的聊天记录集合"""
    name = _collection_name(user_id)
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _make_id(session_id: str, question: str) -> str:
    """生成唯一 ID"""
    raw = f"{session_id}:{question}:{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()


def store_qa(session_id: str, question: str, answer: str, sources: list = None, user_id: int = None):
    """
    存储一条问答记录

    Args:
        session_id: 会话 ID
        question: 用户问题
        answer: 助手回答
        sources: 引用来源列表（可选）
        user_id: 用户 ID（用于按用户隔离集合）
    """
    if user_id is None:
        logger.warning("store_qa 缺少 user_id，跳过存储")
        return

    collection = _get_collection(user_id)

    doc_text = f"问题：{question}\n回答：{answer}"

    source_summary = ""
    if sources:
        source_parts = [f"{s.get('source', '')}第{s.get('page', '?')}页" for s in sources[:3]]
        source_summary = "；".join(source_parts)

    doc_id = _make_id(session_id, question)
    embedding = embed_texts([doc_text])[0]

    metadata = {
        "session_id": session_id,
        "question": question,
        "answer": answer[:500],
        "sources": source_summary,
        "timestamp": time.time(),
    }

    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[doc_text],
        metadatas=[metadata],
    )
    logger.debug("聊天记录已存储: user=%d session=%s question='%s'", user_id, session_id, question[:50])


def search_history(query: str, top_k: int = 5, exclude_session: str = None, user_id: int = None) -> list:
    """
    语义检索当前用户的历史聊天记录

    Args:
        query: 查询文本
        top_k: 返回数量
        exclude_session: 排除的会话 ID（避免重复检索当前会话）
        user_id: 用户 ID（必须传入，否则返回空）

    Returns:
        [{"question": str, "answer": str, "session_id": str, "score": float, "sources": str}]
    """
    if user_id is None:
        logger.warning("search_history 缺少 user_id，跳过检索")
        return []

    collection = _get_collection(user_id)

    if collection.count() == 0:
        return []

    where_filter = None
    if exclude_session:
        where_filter = {"session_id": {"$ne": exclude_session}}

    query_embedding = embed_query(query)
    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k * 2, collection.count()),
        "include": ["metadatas", "distances"],
    }
    if where_filter:
        query_params["where"] = where_filter

    results = collection.query(**query_params)

    history = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        score = max(0.0, 1.0 - dist)
        history.append({
            "question": meta.get("question", ""),
            "answer": meta.get("answer", ""),
            "session_id": meta.get("session_id", ""),
            "sources": meta.get("sources", ""),
            "score": score,
        })

    return history[:top_k]


def delete_by_session(session_id: str, user_id: int = None) -> int:
    """删除指定会话的所有聊天记录"""
    if user_id is None:
        logger.warning("delete_by_session 缺少 user_id，跳过")
        return 0

    collection = _get_collection(user_id)
    try:
        results = collection.get(
            where={"session_id": session_id},
            include=[],
        )
        if results and results["ids"]:
            count = len(results["ids"])
            collection.delete(ids=results["ids"])
            logger.info("删除会话聊天记录: user=%d session=%s count=%d", user_id, session_id, count)
            return count
        return 0
    except Exception as e:
        logger.warning("删除会话聊天记录失败: session=%s — %s", session_id, str(e))
        return 0


def delete_by_user(user_id: int) -> int:
    """删除指定用户的整个聊天记录集合"""
    name = _collection_name(user_id)
    try:
        client = get_chroma_client()
        client.delete_collection(name=name)
        logger.info("删除用户聊天集合: %s", name)
        return 1
    except Exception as e:
        logger.warning("删除用户聊天集合失败: %s — %s", name, str(e))
        return 0


def clear_legacy_collection() -> int:
    """
    清理旧版共享 chat_history 集合（一次性迁移用）

    旧版所有用户共用一个 chat_history 集合，
    新版每个用户独立 chat_{user_id} 集合。
    调用此函数删除旧集合。
    """
    try:
        client = get_chroma_client()
        try:
            collection = client.get_collection(name=_LEGACY_COLLECTION_NAME)
            count = collection.count()
        except Exception:
            logger.info("旧版 chat_history 集合不存在，无需清理")
            return 0

        client.delete_collection(name=_LEGACY_COLLECTION_NAME)
        logger.info("已清理旧版 chat_history 集合: %d 条记录", count)
        return count
    except Exception as e:
        logger.warning("清理旧版集合失败: %s", str(e))
        return 0


def get_stats(user_id: int = None) -> dict:
    """获取聊天记录统计"""
    if user_id is None:
        return {"total_records": 0, "collection_name": "N/A"}
    collection = _get_collection(user_id)
    return {
        "total_records": collection.count(),
        "collection_name": _collection_name(user_id),
    }

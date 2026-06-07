"""
聊天记录向量存储模块
负责: RAG

将聊天问答对存入独立的 Chroma 集合（与 PDF 文档向量分离），
支持语义检索历史对话，增强多轮对话记忆。
"""

import hashlib
import time

from src.data.vector_store import get_chroma_client, embed_texts, embed_query
from src.logger import get_logger

logger = get_logger("rag.chat_history_store")

# 聊天记录专用集合名
COLLECTION_NAME = "chat_history"


def _get_collection():
    """获取聊天记录集合"""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _make_id(session_id: str, question: str) -> str:
    """生成唯一 ID"""
    raw = f"{session_id}:{question}:{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()


def store_qa(session_id: str, question: str, answer: str, sources: list = None):
    """
    存储一条问答记录

    Args:
        session_id: 会话 ID
        question: 用户问题
        answer: 助手回答
        sources: 引用来源列表（可选）
    """
    collection = _get_collection()

    # 将问答对组合为一个文档，用于语义检索
    doc_text = f"问题：{question}\n回答：{answer}"

    # 来源摘要
    source_summary = ""
    if sources:
        source_parts = [f"{s.get('source', '')}第{s.get('page', '?')}页" for s in sources[:3]]
        source_summary = "；".join(source_parts)

    doc_id = _make_id(session_id, question)
    embedding = embed_texts([doc_text])[0]

    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[doc_text],
        metadatas=[{
            "session_id": session_id,
            "question": question,
            "answer": answer[:500],  # 元数据中存摘要
            "sources": source_summary,
            "timestamp": time.time(),
            "type": "chat_history",
        }],
    )
    logger.debug("聊天记录已存储: session=%s question='%s'", session_id, question[:50])


def search_history(query: str, top_k: int = 5, exclude_session: str = None) -> list:
    """
    语义检索历史聊天记录

    Args:
        query: 查询文本
        top_k: 返回数量
        exclude_session: 排除的会话 ID（避免重复检索当前会话）

    Returns:
        [{"question": str, "answer": str, "session_id": str, "score": float, "sources": str}]
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["metadatas", "distances"],
    )

    history = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        # 排除当前会话
        if exclude_session and meta.get("session_id") == exclude_session:
            continue
        score = max(0.0, 1.0 - dist)
        history.append({
            "question": meta.get("question", ""),
            "answer": meta.get("answer", ""),
            "session_id": meta.get("session_id", ""),
            "sources": meta.get("sources", ""),
            "score": score,
        })

    return history


def delete_by_session(session_id: str) -> int:
    """删除指定会话的所有聊天记录"""
    collection = _get_collection()
    try:
        results = collection.get(
            where={"session_id": session_id},
            include=[],
        )
        if results and results["ids"]:
            count = len(results["ids"])
            collection.delete(ids=results["ids"])
            logger.info("删除会话聊天记录: session=%s count=%d", session_id, count)
            return count
        return 0
    except Exception as e:
        logger.warning("删除会话聊天记录失败: %s — %s", session_id, str(e))
        return 0


def get_stats() -> dict:
    """获取聊天记录统计"""
    collection = _get_collection()
    return {
        "total_records": collection.count(),
        "collection_name": COLLECTION_NAME,
    }

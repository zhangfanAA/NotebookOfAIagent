"""
智能学习助手 — Chroma 向量数据库操作
负责: RAG
任务: TASK-DATA-004, TASK-FEAT-004

封装 Chroma 向量库的初始化、入库、检索操作。
使用 ONNX Runtime 推理 BAAI/bge-small-zh-v1.5 嵌入模型（轻量，无需 torch）。
"""

import os
import numpy as np

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from src.config import get_config
from src.logger import get_logger

logger = get_logger("data.vector_store")

# 懒加载单例
_embedder = None
_chroma_client = None
_collection = None
_search_cache = {}
_cache_max_size = 100

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "bge-small-zh-v1.5-onnx")


def _get_embedder():
    """懒加载 ONNX 嵌入器（首次调用时加载，~100MB）"""
    global _embedder
    if _embedder is not None:
        return _embedder

    import onnxruntime as ort
    from tokenizers import Tokenizer

    if not os.path.exists(os.path.join(MODEL_DIR, "model.onnx")):
        raise FileNotFoundError(
            f"ONNX 模型未找到: {MODEL_DIR}\n"
            "请先运行模型导出脚本。"
        )

    logger.info("加载 ONNX 嵌入模型: %s", MODEL_DIR)
    tokenizer = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(length=512)
    # 禁用内存 arena，避免 ONNX 推理后内存不释放（从 2.3GB 降到 ~100MB）
    opts = ort.SessionOptions()
    opts.enable_cpu_mem_arena = False
    session = ort.InferenceSession(
        os.path.join(MODEL_DIR, "model.onnx"),
        sess_options=opts,
        providers=["CPUExecutionProvider"],
    )
    _embedder = {"tokenizer": tokenizer, "session": session}
    logger.info("ONNX 嵌入模型加载完成")
    return _embedder


def _encode(texts: list) -> list:
    """批量文本向量化（ONNX 推理）"""
    embedder = _get_embedder()
    tokenizer = embedder["tokenizer"]
    session = embedder["session"]

    encoded = tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    outputs = session.run(None, {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    })

    last_hidden = outputs[0]
    mask = attention_mask[:, :, np.newaxis]
    pooled = (last_hidden * mask).sum(axis=1) / mask.sum(axis=1)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    embeddings = pooled / norms
    return embeddings.tolist()


def embed_texts(texts: list) -> list:
    """批量文本向量化"""
    return _encode(texts)


def embed_query(text: str) -> list:
    """单条查询向量化"""
    return _encode([text])[0]


def get_chroma_client():
    """获取 Chroma 客户端单例（本地持久化）"""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        from chromadb.config import Settings
        config = get_config()["vector_store"]
        persist_dir = config["persist_dir"]
        logger.info("初始化 Chroma 客户端: persist_dir=%s", persist_dir)
        _chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_collection(user_id: int = None, name: str = None):
    """
    获取或创建集合

    Args:
        user_id: 用户 ID，不为 None 时返回 docs_{user_id} 集合（按用户隔离）
        name: 集合名称，显式指定时忽略 user_id
    """
    if name is None:
        if user_id is not None:
            name = f"docs_{user_id}"
        else:
            name = get_config()["vector_store"]["collection_name"]
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.debug("集合就绪: %s (当前文档数: %d)", name, collection.count())
    return collection


def ingest_chunks(chunks: list, user_id: int = None, collection_name: str = None, replace: bool = True) -> int:
    """
    将分块数据入库

    Args:
        chunks: chunker.chunk_text() 或 chunk_pages() 的输出
        user_id: 用户 ID，用于隔离 collection
        collection_name: 集合名称，显式指定时忽略 user_id
        replace: 如果 True，同名文件的旧 chunks 会被删除后重新入库（增量更新）

    Returns:
        入库的块数
    """
    if not chunks:
        logger.warning("没有数据可入库")
        return 0

    collection = get_collection(user_id=user_id, name=collection_name)

    if replace and chunks:
        source_name = chunks[0].get("source", "")
        if source_name:
            delete_by_source(source_name, user_id=user_id, collection_name=collection_name)

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "source": c["source"],
            "page": c["page"],
            "file_type": c.get("file_type", "unknown"),
        }
        for c in chunks
    ]

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        end = min(i + batch_size, len(chunks))
        batch_docs = documents[i:end]
        embeddings = embed_texts(batch_docs)
        collection.add(
            ids=ids[i:end],
            documents=batch_docs,
            metadatas=metadatas[i:end],
            embeddings=embeddings,
        )
        logger.info("入库批次 %d-%d / %d", i, end, len(chunks))

    logger.info("入库完成: %d chunks, 集合总文档数: %d", len(chunks), collection.count())
    return len(chunks)


def delete_by_source(source_name: str, user_id: int = None, collection_name: str = None) -> int:
    """删除指定来源文件的所有 chunks"""
    collection = get_collection(user_id=user_id, name=collection_name)
    try:
        results = collection.get(where={"source": source_name}, include=[])
        if results and results["ids"]:
            count = len(results["ids"])
            collection.delete(ids=results["ids"])
            logger.info("删除旧 chunks: source=%s count=%d", source_name, count)
            return count
        return 0
    except Exception as e:
        logger.warning("删除旧 chunks 失败: %s", str(e))
        return 0


def search(query: str, user_id: int = None, top_k: int = None) -> list:
    """向量相似度检索（带缓存）"""
    if top_k is None:
        top_k = get_config()["agent"]["retrieve_top_k"]

    cache_key = f"{user_id}:{query}:{top_k}"
    if cache_key in _search_cache:
        logger.debug("缓存命中: query='%s'", query[:50])
        return _search_cache[cache_key]

    collection = get_collection(user_id=user_id)

    if collection.count() == 0:
        logger.warning("向量库为空，无法检索")
        return []

    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    search_results = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = max(0.0, 1.0 - dist)
        search_results.append({
            "content": doc,
            "metadata": meta,
            "score": round(score, 4),
        })

    logger.debug("检索完成: query='%s' → %d results (top score=%.4f)",
                 query[:50], len(search_results),
                 search_results[0]["score"] if search_results else 0)

    if len(_search_cache) >= _cache_max_size:
        oldest_key = next(iter(_search_cache))
        del _search_cache[oldest_key]
    _search_cache[cache_key] = search_results

    return search_results


def clear_search_cache():
    """清空搜索缓存"""
    global _search_cache
    _search_cache.clear()
    logger.info("搜索缓存已清空")


def get_stats(user_id: int = None) -> dict:
    """获取向量库统计信息"""
    collection = get_collection(user_id=user_id)
    return {
        "total_chunks": collection.count(),
        "collection_name": collection.name,
    }

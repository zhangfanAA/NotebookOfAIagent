"""
智能学习助手 — Chroma 向量数据库操作
负责: RAG
任务: TASK-DATA-004, TASK-FEAT-004

封装 Chroma 向量库的初始化、入库、检索操作。
使用中文优化嵌入模型 BAAI/bge-small-zh-v1.5。

注意: sentence_transformers 必须在 PyTorch 与其他原生库交互前加载，
否则 Windows 上会出现 segfault。因此模型在模块导入时即预加载。
"""

import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# === 必须在 chromadb 等其他原生库之前加载 PyTorch 模型 ===
from sentence_transformers import SentenceTransformer
_CHINESE_MODEL = SentenceTransformer("BAAI/bge-small-zh-v1.5")
# ===========================================================

import chromadb
from chromadb.config import Settings
from functools import lru_cache

from src.config import get_config
from src.logger import get_logger

logger = get_logger("data.vector_store")

# 全局单例
_chroma_client = None
_collection = None
_search_cache = {}
_cache_max_size = 100


def embed_texts(texts: list) -> list:
    """批量文本向量化（中文模型）"""
    embeddings = _CHINESE_MODEL.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(text: str) -> list:
    """单条查询向量化"""
    embedding = _CHINESE_MODEL.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()


def get_chroma_client() -> chromadb.ClientAPI:
    """获取 Chroma 客户端单例（本地持久化）"""
    global _chroma_client
    if _chroma_client is None:
        config = get_config()["vector_store"]
        persist_dir = config["persist_dir"]
        logger.info("初始化 Chroma 客户端: persist_dir=%s", persist_dir)
        _chroma_client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_collection(name: str = None) -> chromadb.Collection:
    """获取或创建集合（不传 embedding_function，手动管理向量化）"""
    global _collection
    if name is None:
        name = get_config()["vector_store"]["collection_name"]
    client = get_chroma_client()
    _collection = client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("集合就绪: %s (当前文档数: %d)", name, _collection.count())
    return _collection


def ingest_chunks(chunks: list, collection_name: str = None, replace: bool = True) -> int:
    """
    将分块数据入库

    Args:
        chunks: chunker.chunk_text() 或 chunk_pages() 的输出
        collection_name: 集合名称，默认从配置读取
        replace: 如果 True，同名文件的旧 chunks 会被删除后重新入库（增量更新）

    Returns:
        入库的块数
    """
    if not chunks:
        logger.warning("没有数据可入库")
        return 0

    collection = get_collection(collection_name)

    # 增量更新：先删除同名文件的旧 chunks
    if replace and chunks:
        source_name = chunks[0].get("source", "")
        if source_name:
            delete_by_source(source_name, collection_name)

    # 准备数据
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

    # 批量入库（手动向量化后传入 embeddings）
    batch_size = 200
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


def delete_by_source(source_name: str, collection_name: str = None) -> int:
    """
    删除指定来源文件的所有 chunks（TASK-PERF-002 增量更新）

    Args:
        source_name: 文件名
        collection_name: 集合名称

    Returns:
        删除的块数
    """
    collection = get_collection(collection_name)
    try:
        results = collection.get(
            where={"source": source_name},
            include=[],
        )
        if results and results["ids"]:
            count = len(results["ids"])
            collection.delete(ids=results["ids"])
            logger.info("删除旧 chunks: source=%s count=%d", source_name, count)
            return count
        return 0
    except Exception as e:
        logger.warning("删除旧 chunks 失败: %s", str(e))
        return 0


def search(query: str, top_k: int = None) -> list:
    """
    向量相似度检索（带缓存）

    Args:
        query: 查询文本
        top_k: 返回数量，默认从配置读取

    Returns:
        [
            {
                "content": str,         # 文档片段内容
                "metadata": dict,       # 元数据
                "score": float          # 相似度分数 (0-1, 越高越相关)
            }
        ]
    """
    if top_k is None:
        top_k = get_config()["agent"]["retrieve_top_k"]

    # 检查缓存
    cache_key = f"{query}:{top_k}"
    if cache_key in _search_cache:
        logger.debug("缓存命中: query='%s'", query[:50])
        return _search_cache[cache_key]

    collection = get_collection()

    # 检查向量库是否为空
    if collection.count() == 0:
        logger.warning("向量库为空，无法检索")
        return []

    # 检索（手动向量化 query）
    query_embedding = embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    # 整理结果（Chroma 返回的 distance 越小越相似，转换为 score）
    search_results = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = max(0.0, 1.0 - dist)  # cosine distance → similarity score
        search_results.append({
            "content": doc,
            "metadata": meta,
            "score": round(score, 4),
        })

    logger.debug("检索完成: query='%s' → %d results (top score=%.4f)",
                 query[:50], len(search_results),
                 search_results[0]["score"] if search_results else 0)

    # 存入缓存（限制大小）
    if len(_search_cache) >= _cache_max_size:
        # 删除最早的缓存项
        oldest_key = next(iter(_search_cache))
        del _search_cache[oldest_key]
    _search_cache[cache_key] = search_results

    return search_results


def clear_search_cache():
    """清空搜索缓存"""
    global _search_cache
    _search_cache.clear()
    logger.info("搜索缓存已清空")


def get_stats() -> dict:
    """获取向量库统计信息"""
    collection = get_collection()
    return {
        "total_chunks": collection.count(),
        "collection_name": collection.name,
    }

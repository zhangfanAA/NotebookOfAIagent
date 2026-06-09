"""
LangGraph 检索节点 (Retrieve)
负责: RAG
任务: TASK-AGENT-001

在 Chroma 向量库中执行相似度搜索，返回 Top-K 相关文档片段。
"""

from src.rag.state import AgentState
from src.data import vector_store
from src.logger import get_logger

logger = get_logger("rag.retrieve")


def retrieve_node(state: AgentState) -> dict:
    """
    检索节点

    输入: state["question"] 或 state["rewritten_query"]
    输出: state["documents"]

    逻辑:
    1. 优先使用 rewritten_query（如存在），否则用原始 question
    2. 在 Chroma 中执行相似度搜索
    3. 返回 Top-K 相关文档片段
    """
    # 优先使用重写后的查询
    query = state.get("rewritten_query") or state["question"]
    top_k = state.get("max_loops", 3) + 2  # 至少返回 5 个

    user_id = state.get("user_id")

    logger.info("[检索节点] 查询: '%s' (top_k=%d, user_id=%s)", query[:80], top_k, user_id)

    try:
        results = vector_store.search(query, user_id=user_id, top_k=top_k)
    except Exception as e:
        logger.error("[检索节点] 检索失败: %s", str(e))
        results = []

    if not results:
        logger.warning("[检索节点] 未检索到任何文档")

    return {"documents": results}

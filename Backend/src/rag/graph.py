"""
LangGraph 图组装与状态管理
负责: RAG
任务: TASK-AGENT-005

将四个节点组装为完整的 LangGraph 状态机，实现条件边路由。

图结构:
  START → retrieve → grade
  grade → (yes) → generate → END
  grade → (no, loops < max) → rewrite → retrieve（循环）
  grade → (no, loops >= max) → generate（强制兜底）
"""

from src.logger import get_logger

logger = get_logger("rag.graph")


def _should_generate(state: AgentState) -> str:
    """
    评估节点后的路由判断

    - relevance == "yes" → 生成答案
    - relevance == "no" 且循环次数 < max_loops → 重写查询重试
    - relevance == "no" 且循环次数 >= max_loops → 强制生成兜底答案
    """
    relevance = state.get("relevance", "no")
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 3)

    if relevance == "yes":
        logger.info("[路由] 相关 → 生成节点")
        return "generate"

    if loop_count >= max_loops:
        logger.info("[路由] 不相关但达到循环上限(%d/%d) → 强制生成", loop_count, max_loops)
        return "generate"

    logger.info("[路由] 不相关 → 重写节点 (loop=%d/%d)", loop_count, max_loops)
    return "rewrite"


def build_graph():
    """
    构建 LangGraph 状态机

    Returns:
        编译好的 LangGraph 图，可直接调用 .invoke()
    """
    from langgraph.graph import StateGraph, END
    from src.rag.state import AgentState
    from src.rag.retrieve import retrieve_node
    from src.rag.grade import grade_node
    from src.rag.generate import generate_node
    from src.rag.rewrite import rewrite_node

    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("generate", generate_node)
    graph.add_node("rewrite", rewrite_node)

    # 定义边
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "grade")

    # 条件边: grade → generate 或 rewrite
    graph.add_conditional_edges(
        "grade",
        _should_generate,
        {
            "generate": "generate",
            "rewrite": "rewrite",
        },
    )

    # rewrite → retrieve（形成闭环）
    graph.add_edge("rewrite", "retrieve")

    # generate → END
    graph.add_edge("generate", END)

    # 编译
    compiled = graph.compile()
    logger.info("LangGraph 状态机编译完成")
    return compiled


# 全局编译图单例
_compiled_graph = None


def get_graph():
    """获取编译好的图单例"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph

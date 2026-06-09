"""
LangGraph 状态定义
所有节点间流转的状态字典在此统一定义
"""

from typing import TypedDict, List, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态机的状态字典"""

    # 用户原始问题
    question: str

    # 重写后的检索查询（重写节点输出）
    rewritten_query: Optional[str]

    # 检索到的文档片段列表
    documents: Optional[List[dict]]

    # 评估结果: "yes" / "no"
    relevance: Optional[str]

    # 最终生成的答案
    answer: Optional[str]

    # 引用来源列表
    sources: Optional[List[dict]]

    # 推理过程
    reasoning: Optional[str]

    # 置信度 0-1
    confidence: Optional[float]

    # 对话历史（自动追加）
    messages: Annotated[list, add_messages]

    # 循环计数器（防止死循环）
    loop_count: int

    # 最大循环次数
    max_loops: int

    # 会话 ID
    session_id: str

    # 用户 ID（用于向量库隔离）
    user_id: Optional[int]

    # 用户级 LLM 客户端（可选，优先使用）
    llm_client: Optional[object]

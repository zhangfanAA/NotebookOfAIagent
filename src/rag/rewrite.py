"""
LangGraph 重写节点 (Rewrite Query)
负责: RAG
任务: TASK-AGENT-004

分析检索失败原因，将模糊查询重写为更适合向量检索的具体查询。
"""

from src.rag.state import AgentState
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.rewrite")

# 重写 Prompt
REWRITE_PROMPT = """你是一个查询优化专家。学生向学习助手提出了一个问题，但系统没有检索到相关文档。

## 你的任务
分析原始问题为什么检索失败，并重写为更适合向量检索的查询。

## 重写策略
1. 将口语化/模糊的表达转化为更精确的学术/技术术语
2. 补充关键的上下文信息（如课程名、编程语言、章节主题等）
3. 去掉无关的口语化词汇
4. 如果原问题涉及具体代码或公式，提取核心概念

## 原始问题
{question}

## 之前检索到的文档（不相关）
{documents}

## 请输出重写后的查询（只输出查询文本，不要解释）:"""

# 全局 LLM 客户端
_llm_client = None


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def rewrite_node(state: AgentState) -> dict:
    """
    重写节点

    输入: state["question"] + state["documents"] + state["loop_count"]
    输出: state["rewritten_query"], loop_count += 1

    策略:
    1. 调用 LLM 分析原问题并重写
    2. 递增循环计数器
    3. 如果 LLM 重写失败，使用简单的关键词扩展作为降级
    """
    question = state["question"]
    documents = state.get("documents", [])
    loop_count = state.get("loop_count", 0) + 1

    logger.info("[重写节点] 开始重写查询 (loop=%d): '%s'", loop_count, question[:80])

    # 拼接之前不相关的文档
    doc_text = "无" if not documents else "\n".join(
        d["content"][:100] for d in documents[:2]
    )

    # 调用 LLM 重写
    try:
        llm = _get_llm()
        rewritten = llm.chat(
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(
                question=question,
                documents=doc_text,
            )}],
            temperature=0.3,
            max_tokens=200,
        )
        rewritten = rewritten.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("[重写节点] LLM 重写失败，使用降级策略: %s", str(e))
        rewritten = _fallback_rewrite(question)

    logger.info("[重写节点] 重写结果: '%s'", rewritten[:80])

    return {
        "rewritten_query": rewritten,
        "loop_count": loop_count,
    }


def _fallback_rewrite(question: str) -> str:
    """
    降级重写策略（LLM 不可用时）

    简单地在原始问题前后补充通用关键词
    """
    # 去掉常见口语化前缀
    prefixes_to_remove = [
        "请问", "请帮我", "帮我", "我想问", "我想知道",
        "那个", "怎么", "如何",
    ]
    cleaned = question
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    # 补充关键词
    return f"{cleaned} 概念 用法 原理 示例"

"""
LangGraph 评估节点 (Grade Relevance)
负责: RAG
任务: TASK-AGENT-002

使用 LLM 判断检索结果是否与问题相关。
输出 "yes" 或 "no"，temperature=0 确保稳定。

兜底策略: 当检索分数 >= 阈值时，即使 LLM 判 no 也强制通过。
"""

import re

from src.rag.state import AgentState
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.grade")

# 检索分数阈值：高于此分数直接判定相关（跳过 LLM 评估）
SCORE_THRESHOLD = 0.50

# 评估 Prompt
GRADE_PROMPT = """你是一个文档相关性评估专家。

## 任务
判断以下检索到的文档是否能帮助回答用户的问题。
只输出 "yes" 或 "no"，不要输出任何其他内容。

## 判断标准（宽松）
- 只要文档内容与问题主题有关联，就输出 "yes"
- 只有文档内容完全无关时才输出 "no"
- 即使文档只是部分相关，也应该输出 "yes"

## 用户问题
{question}

## 检索到的文档
{documents}

## 你的判断（只输出 yes 或 no）:"""

# 全局 LLM 客户端
_llm_client = None


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def grade_node(state: AgentState) -> dict:
    """
    评估节点

    输入: state["question"] + state["documents"]
    输出: state["relevance"] = "yes" / "no"

    容错:
    - 如果 documents 为空，直接返回 "no"
    - 如果最高检索分数 >= 阈值，直接返回 "yes"（跳过 LLM）
    - LLM 输出不规范时用正则提取 yes/no，默认 "no"
    """
    question = state["question"]
    documents = state.get("documents", [])

    # 无文档直接判 no
    if not documents:
        logger.info("[评估节点] 无检索文档，直接判定 no")
        return {"relevance": "no"}

    # 检索分数兜底：如果最高分 >= 阈值，直接判 yes
    max_score = max(d.get("score", 0) for d in documents)
    if max_score >= SCORE_THRESHOLD:
        logger.info("[评估节点] 检索分数 %.4f >= %.2f，直接判定 yes", max_score, SCORE_THRESHOLD)
        return {"relevance": "yes"}

    # LLM 评估
    doc_text = "\n\n---\n\n".join(
        f"[文档{i+1}] {d['content'][:300]}" for i, d in enumerate(documents[:3])
    )

    prompt = GRADE_PROMPT.format(question=question, documents=doc_text)

    try:
        llm = state.get("llm_client") or _get_llm()
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
    except Exception as e:
        logger.error("[评估节点] LLM 调用失败: %s", str(e))
        # LLM 失败时，根据分数兜底
        if max_score >= 0.35:
            logger.info("[评估节点] LLM 失败但分数 %.4f 尚可，判定 yes", max_score)
            return {"relevance": "yes"}
        return {"relevance": "no"}

    # 提取 yes/no（容错处理）
    relevance = _parse_relevance(response)
    logger.info("[评估节点] 判定: %s (原始输出: '%s')", relevance, response.strip()[:50])

    return {"relevance": relevance}


def _parse_relevance(response: str) -> str:
    """
    从 LLM 输出中提取 yes/no

    容错策略:
    1. 先尝试精确匹配
    2. 再用正则提取
    3. 默认返回 "no"（偏保守，宁可重写也不生成错误答案）
    """
    cleaned = response.strip().lower()

    # 精确匹配
    if cleaned in ("yes", "no"):
        return cleaned

    # 正则提取（处理 "yes." "答案是yes" 等情况）
    match = re.search(r'\b(yes|no)\b', cleaned)
    if match:
        return match.group(1)

    # 含义匹配
    if any(word in cleaned for word in ["是", "相关", "可以", "能", "有帮助"]):
        return "yes"
    if any(word in cleaned for word in ["否", "不相关", "无法", "没有", "不匹配"]):
        return "no"

    return "no"  # 默认保守

"""
LangGraph 生成节点 (Generate)
负责: RAG
任务: TASK-AGENT-003

结合检索到的文档和问题，生成带引用来源的 Markdown 格式答案。
"""

from src.rag.state import AgentState
from src.rag.llm_client import LLMClient
from src.utils.security import build_safe_system_prompt
from src.logger import get_logger

logger = get_logger("rag.generate")

# 生成 Prompt
GENERATE_PROMPT = """你是一个专业的学习助手。你必须基于下方参考资料来回答问题。

## 强制规则（违反则回答无效）
1. **每个知识点、每个段落都必须标注来源**，格式为 [1] [2] [3]
2. 引用编号对应下方参考资料的编号，例如 [1] 对应"参考资料 1"
3. 不得编造信息，不得使用未在参考资料中出现的来源编号
4. 使用 Markdown 格式，适当使用标题、列表、表格

## 参考资料
{context}

## 用户问题
{question}

## 回答要求
- 每句话结尾或关键知识点后必须加 [编号]
- 示例格式："TCP 有三次握手 [1]，拥塞控制包括慢开始和拥塞避免 [2][3]"
- 如果参考资料不足以回答，说明哪些部分可以回答并标注来源，哪些不确定

请开始回答（Markdown格式，每个知识点必须标注来源编号）："""

# 无法回答时的兜底 Prompt
FALLBACK_PROMPT = """你是一个学习助手。以下参考资料中没有找到与用户问题直接相关的内容。
请礼貌地告知用户当前知识库中未找到相关信息，建议他们：
1. 换一种方式描述问题
2. 上传相关课件资料
3. 检查问题是否在已上传的课程范围内

用户问题: {question}

请用简洁友好的语气回复:"""

# 全局 LLM 客户端
_llm_client = None


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def generate_node(state: AgentState) -> dict:
    """
    生成节点

    输入: state["question"] + state["documents"]
    输出: state["answer"], state["sources"], state["reasoning"], state["confidence"]

    策略:
    - 有相关文档时：结合文档生成带引用的答案
    - 无相关文档时（循环耗尽）：生成友好的兜底回答
    """
    question = state["question"]
    documents = state.get("documents", [])
    relevance = state.get("relevance", "no")
    loop_count = state.get("loop_count", 0)

    llm = state.get("llm_client") or _get_llm()

    # 如果文档不相关或为空，生成兜底回答
    if relevance == "no" or not documents:
        logger.info("[生成节点] 文档不相关，生成兜底回答 (loop=%d)", loop_count)
        try:
            answer = llm.chat(
                messages=[{"role": "user", "content": FALLBACK_PROMPT.format(question=question)}],
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("[生成节点] 兜底回答生成失败: %s", str(e))
            answer = "抱歉，我暂时无法回答这个问题。建议您换一种方式提问，或上传相关的课程资料。"

        return {
            "answer": answer,
            "sources": [],
            "reasoning": f"经过 {loop_count} 次检索，未找到与问题直接相关的文档",
            "confidence": 0.1,
            "loop_count": loop_count,
        }

    # 构建上下文
    context_parts = []
    sources_list = []
    seen_sources = set()
    for i, doc in enumerate(documents):
        source_name = doc.get("metadata", {}).get("source", "未知来源")
        page = doc.get("metadata", {}).get("page", "?")
        score = doc.get("score", 0)
        content = doc["content"]

        # 去重：同一来源+页码+内容前100字只保留一条
        dedup_key = (source_name, page, content[:100])
        if dedup_key in seen_sources:
            continue
        seen_sources.add(dedup_key)

        context_parts.append(f"【参考资料 {i+1}】来源:《{source_name}》第{page}页\n{content}")
        sources_list.append({
            "content": content[:200],
            "source": source_name,
            "page": page,
            "score": score,
        })

    context = "\n\n---\n\n".join(context_parts)

    # 生成答案
    prompt = GENERATE_PROMPT.format(context=context, question=question)
    safe_system_prompt = build_safe_system_prompt()

    try:
        answer = llm.chat(
            messages=[
                {"role": "system", "content": safe_system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
    except Exception as e:
        logger.error("[生成节点] LLM 调用失败: %s", str(e))
        answer = "抱歉，生成回答时出现错误，请稍后重试。"
        return {
            "answer": answer,
            "sources": sources_list,
            "reasoning": f"LLM 调用失败: {str(e)}",
            "confidence": 0.0,
            "loop_count": loop_count,
        }

    # 评估置信度（基于文档相关度分数）
    avg_score = sum(s["score"] for s in sources_list) / len(sources_list) if sources_list else 0
    confidence = min(1.0, avg_score * 1.2)  # 略微放大，但不超过 1

    reasoning = (
        f"基于 {len(documents)} 个相关文档生成回答，"
        f"平均相关度 {avg_score:.2f}，"
        f"循环次数 {loop_count}"
    )

    logger.info(
        "[生成节点] 回答生成完成: %d docs, confidence=%.2f, loop=%d",
        len(documents), confidence, loop_count,
    )

    return {
        "answer": answer,
        "sources": sources_list,
        "reasoning": reasoning,
        "confidence": round(confidence, 2),
        "loop_count": loop_count,
    }

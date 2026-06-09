"""
MCP Server — 学习工具生成器

工具:
- generate_mindmap     — 生成思维导图或重点笔记
- generate_quiz        — 生成测验题目
- check_quiz_answer    — 判分
- generate_flashcards  — 生成闪卡
- compare_documents    — 文档对比

启动方式: python -m src.mcp_servers.learning_tools_server
"""

from mcp.server.fastmcp import FastMCP

from src.mcp_servers._common import get_rag_service, get_user_llm, run_blocking, to_json_string

mcp = FastMCP(
    "SmartRead-Learning",
    instructions="学习工具：思维导图、测验、闪卡、文档对比生成器",
)


@mcp.tool()
async def generate_mindmap(
    file_names: list[str],
    user_id: int,
    user_prompt: str = "",
    output_type: str = "mindmap",
) -> str:
    """基于已上传文档生成思维导图或重点笔记。

    Args:
        file_names: 文档文件名列表（必须是已上传的文档）
        user_id: 用户 ID
        user_prompt: 额外的生成提示（可选）
        output_type: 'mindmap' 生成 JSON 节点树 + Mermaid 代码，'notes' 生成 Markdown 笔记

    Returns:
        JSON 字符串，包含生成内容、Mermaid 代码（思维导图模式）等
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    result = await run_blocking(
        rag.generate_content, file_names, user_prompt, output_type, user_llm
    )
    return to_json_string(result)


@mcp.tool()
async def generate_quiz(
    file_names: list[str],
    user_id: int,
    num_questions: int = 5,
    difficulty: str = "medium",
    qtypes: list[str] = None,
) -> str:
    """基于已上传文档生成测验题目。

    Args:
        file_names: 文档文件名列表
        user_id: 用户 ID
        num_questions: 题目数量（默认 5）
        difficulty: 难度 'easy'/'medium'/'hard'
        qtypes: 题型列表，如 ['choice', 'fill', 'short_answer']（默认全部题型）

    Returns:
        JSON 字符串，包含题目列表（每题含类型、题目、答案、解析）
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    if qtypes is None:
        qtypes = ["choice", "fill", "short_answer"]
    result = await run_blocking(
        rag.generate_quiz, file_names, num_questions, difficulty, qtypes, user_llm
    )
    return to_json_string(result)


@mcp.tool()
async def check_quiz_answer(question: dict, user_answer: str, user_id: int) -> str:
    """判分：检查用户对测验题目的回答是否正确。

    Args:
        question: 原始题目对象（必须是 generate_quiz 返回的完整题目 dict）
        user_answer: 用户的回答
        user_id: 用户 ID

    Returns:
        JSON 字符串，包含是否正确、正确答案和解析
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    result = await run_blocking(
        rag.check_quiz_answer, question, user_answer, user_llm
    )
    return to_json_string(result)


@mcp.tool()
async def generate_flashcards(
    file_names: list[str],
    user_id: int,
    num_cards: int = 10,
    topic_focus: str = "",
) -> str:
    """基于已上传文档生成闪卡（问答对）。

    Args:
        file_names: 文档文件名列表
        user_id: 用户 ID
        num_cards: 闪卡数量（默认 10）
        topic_focus: 聚焦主题（可选，为空则覆盖全文）

    Returns:
        JSON 字符串，包含闪卡列表（每张含正面、背面、分类）
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    result = await run_blocking(
        rag.generate_flashcards, file_names, num_cards, topic_focus, user_llm
    )
    return to_json_string(result)


@mcp.tool()
async def compare_documents(file_names: list[str], user_id: int, focus: str = "") -> str:
    """对比两个或多个文档，分析异同点。

    Args:
        file_names: 文档文件名列表（至少 2 个）
        user_id: 用户 ID
        focus: 对比焦点（可选，如 '核心观点'、'方法论'）

    Returns:
        JSON 字符串，包含结构化的对比分析结果
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    result = await run_blocking(
        rag.compare_documents, file_names, focus, user_llm
    )
    return to_json_string(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")

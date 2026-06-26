"""
MCP Server — RAG 问答与文档管理

工具:
- rag_query        — 基于已上传文档进行 RAG 智能问答
- list_documents   — 列出用户的已上传文档
- upload_document  — 上传 PDF 文档用于 RAG 索引
- delete_document  — 删除指定文档

启动方式: python -m src.mcp_servers.rag_server
"""

from mcp.server.fastmcp import FastMCP

from src.mcp_servers._common import get_rag_service, get_user_llm, run_blocking, to_json_string

mcp = FastMCP("SmartRead-RAG", instructions="RAG 智能问答与文档管理工具")


@mcp.tool()
async def rag_query(question: str, session_id: str, user_id: int) -> str:
    """基于已上传的学习资料回答问题（RAG 检索增强生成）。

    Args:
        question: 用户提出的问题
        session_id: 会话 ID（必须是已存在的会话，用于管理对话历史）
        user_id: 用户 ID

    Returns:
        JSON 字符串，包含答案文本、引用来源列表和置信度
    """
    rag = get_rag_service()
    user_llm = get_user_llm(user_id)
    result = await run_blocking(
        rag.query, question, session_id, llm_client=user_llm, user_id=user_id
    )
    return to_json_string(result)


@mcp.tool()
async def list_documents(user_id: int) -> str:
    """列出指定用户的所有已上传文档。

    Args:
        user_id: 用户 ID

    Returns:
        JSON 字符串，包含文档列表（id、文件名、状态、切片数等）
    """
    rag = get_rag_service()
    docs = await run_blocking(rag.get_documents, user_id=user_id)
    # 移除 full_text 避免 MCP stdio 传输大数据挂起
    slim_docs = [
        {k: v for k, v in d.items() if k != "full_text"}
        for d in docs
    ]
    return to_json_string({"documents": slim_docs})


@mcp.tool()
async def upload_document(file_path: str, user_id: int, original_filename: str = None) -> str:
    """上传 PDF 文档用于 RAG 索引。文件必须位于服务器本地文件系统。

    Args:
        file_path: PDF 文件的本地路径
        user_id: 用户 ID
        original_filename: 原始文件名（可选，默认使用 file_path 的文件名）

    Returns:
        JSON 字符串，包含上传状态、切片数量等信息
    """
    rag = get_rag_service()
    result = await run_blocking(
        rag.upload_document, file_path, original_filename, user_id
    )
    return to_json_string(result)


@mcp.tool()
async def delete_document(doc_id: int) -> str:
    """删除指定文档（同时删除向量库中的索引）。

    Args:
        doc_id: 文档 ID

    Returns:
        JSON 字符串，包含删除结果
    """
    rag = get_rag_service()
    success = await run_blocking(rag.delete_document, doc_id)
    return to_json_string({"deleted": success, "doc_id": doc_id})


if __name__ == "__main__":
    mcp.run(transport="stdio")

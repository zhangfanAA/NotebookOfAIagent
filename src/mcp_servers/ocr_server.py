"""
MCP Server — OCR 与 PDF 解析

工具:
- ocr_image   — 对图片文件执行 PaddleOCR 文字识别
- parse_pdf   — 解析 PDF 文件，提取每页文本（扫描页自动 OCR）

启动方式: python -m src.mcp_servers.ocr_server
"""

import json
import os
import subprocess
import sys
import tempfile

from mcp.server.fastmcp import FastMCP

from src.mcp_servers._common import run_blocking, to_json_string

mcp = FastMCP("SmartRead-OCR", instructions="OCR 图片识别与 PDF 文本提取工具")


def _run_ocr_on_image(image_path: str) -> str:
    """通过子进程对单张图片执行 PaddleOCR（复用 pdf_parser.py 的子进程模式）"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    result_file = tempfile.mktemp(suffix=".json")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.data._ocr_script", result_file, image_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_root,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"OCR 子进程失败: {proc.stderr[:500]}")
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("results", {}).get("0", "")
        return ""
    finally:
        if os.path.exists(result_file):
            os.unlink(result_file)


@mcp.tool()
async def ocr_image(image_path: str) -> str:
    """对图片文件执行 OCR 文字识别（PaddleOCR）。

    Args:
        image_path: 图片文件的本地路径（必须由服务器可访问）

    Returns:
        JSON 字符串，包含识别文本和来源文件名
    """
    text = await run_blocking(_run_ocr_on_image, image_path)
    return to_json_string({
        "status": "success",
        "text": text,
        "source": os.path.basename(image_path),
    })


@mcp.tool()
async def parse_pdf(pdf_path: str) -> str:
    """解析 PDF 文件，提取每页文本。扫描型页面自动调用 PaddleOCR。

    Args:
        pdf_path: PDF 文件的本地路径

    Returns:
        JSON 字符串，包含总页数、OCR 状态和每页文本摘要（每页最多 500 字）
    """
    from src.data.pdf_parser import parse_pdf as _parse_pdf

    result = await run_blocking(_parse_pdf, pdf_path)

    pages_summary = []
    for p in result.get("pages", []):
        pages_summary.append({
            "page": p["page"],
            "content": p["content"][:500],
            "source": p.get("source", ""),
        })

    return to_json_string({
        "status": "success",
        "total_pages": len(result.get("pages", [])),
        "ocr_skipped": result.get("ocr_skipped", False),
        "pages": pages_summary,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")

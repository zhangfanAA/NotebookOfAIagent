"""
智能学习助手 — PDF 文档解析模块
负责: RAG 文档解析

使用 PyMuPDF 提取 PDF 文本，保留页码和元数据。
支持中英文混合文本和代码块。
"""

from pathlib import Path

import fitz  # PyMuPDF

from src.logger import get_logger

logger = get_logger("data.pdf_parser")


def parse_pdf(file_path: str) -> dict:
    """
    解析 PDF 文件，提取每页文本（纯文字提取，不含 OCR）

    Args:
        file_path: PDF 文件路径

    Returns:
        {
            "pages": [
                {
                    "content": str,     # 该页文本内容
                    "page": int,        # 页码（从 1 开始）
                    "source": str,      # 文件名
                    "file_type": "pdf"
                }
            ],
            "ocr_skipped": False,
            "ocr_skipped_pages": 0,
        }

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件不是有效 PDF
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"文件不是 PDF 格式: {file_path}")

    source_name = path.name

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info("开始解析 PDF: %s (%d 页)", source_name, total_pages)

        pages = []
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text")

            # 清理多余空行
            lines = text.split("\n")
            cleaned_lines = []
            prev_empty = False
            for line in lines:
                stripped = line.rstrip()
                if not stripped:
                    if not prev_empty:
                        cleaned_lines.append("")
                        prev_empty = True
                else:
                    cleaned_lines.append(stripped)
                    prev_empty = False

            content = "\n".join(cleaned_lines).strip()

            if content:
                pages.append({
                    "content": content,
                    "page": page_num + 1,
                    "source": source_name,
                    "file_type": "pdf",
                })

        doc.close()
        logger.info("PDF 解析完成: %s, 有效页数: %d/%d", source_name, len(pages), total_pages)

    except fitz.FileDataError:
        raise ValueError(f"无法打开 PDF 文件（可能已损坏）: {file_path}")
    except Exception as e:
        logger.error("PDF 解析异常: %s — %s", source_name, str(e))
        raise

    return {
        "pages": pages,
        "ocr_skipped": False,
        "ocr_skipped_pages": 0,
    }

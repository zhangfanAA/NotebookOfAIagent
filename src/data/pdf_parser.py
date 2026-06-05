"""
智能学习助手 — PDF 文档解析模块
负责: RAG
任务: TASK-DATA-002

使用 PyMuPDF 提取 PDF 文本，保留页码和元数据。
支持中英文混合文本和代码块。
支持扫描型 PDF 自动 OCR（PaddleOCR）。
"""

import tempfile
import os
from pathlib import Path

import fitz  # PyMuPDF

from src.logger import get_logger

logger = get_logger("data.pdf_parser")

# 扫描页判定阈值：文字少于此数时触发 OCR
OCR_THRESHOLD = 50

# PaddleOCR 全局单例（延迟加载）
_ocr_instance = None


def _get_ocr():
    """延迟加载 PaddleOCR 单例"""
    global _ocr_instance
    if _ocr_instance is None:
        logger.info("首次调用，正在初始化 PaddleOCR...")
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(
            lang="ch",
            use_angle_cls=True,
            show_log=False,
        )
        logger.info("PaddleOCR 初始化完成")
    return _ocr_instance


def _ocr_page(page) -> str:
    """
    对单页 PDF 执行 OCR

    Args:
        page: PyMuPDF page 对象

    Returns:
        OCR 识别出的文本
    """
    # 页面转图片（200 DPI 平衡质量和速度）
    pix = page.get_pixmap(dpi=200)

    # 保存为临时图片
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(tmp_fd)
        pix.save(tmp_path)

        # PaddleOCR 识别
        ocr = _get_ocr()
        result = ocr.ocr(tmp_path, cls=True)

        # 拼接识别结果
        lines = []
        if result and result[0]:
            for line_info in result[0]:
                # line_info: [坐标框, (文字, 置信度)]
                text = line_info[1][0]
                lines.append(text)

        return "\n".join(lines)
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def parse_pdf(file_path: str) -> list:
    """
    解析 PDF 文件，提取每页文本

    自动检测扫描型页面并使用 OCR 识别。

    Args:
        file_path: PDF 文件路径

    Returns:
        [
            {
                "content": str,     # 该页文本内容
                "page": int,        # 页码（从 1 开始）
                "source": str,      # 文件名
                "file_type": "pdf"
            }
        ]

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
    pages = []
    ocr_count = 0

    try:
        doc = fitz.open(file_path)
        logger.info("开始解析 PDF: %s (%d 页)", source_name, len(doc))

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 第一步：尝试正常提取文字
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

            # 第二步：如果文字过少，判定为扫描页，使用 OCR
            if len(content) < OCR_THRESHOLD:
                logger.info("第 %d 页文字过少(%d字)，尝试 OCR 识别", page_num + 1, len(content))
                try:
                    ocr_text = _ocr_page(page)
                    if ocr_text.strip():
                        content = ocr_text.strip()
                        ocr_count += 1
                        logger.info("第 %d 页 OCR 识别成功: %d 字", page_num + 1, len(content))
                    else:
                        logger.warning("第 %d 页 OCR 未识别到文字", page_num + 1)
                except Exception as e:
                    logger.error("第 %d 页 OCR 失败: %s", page_num + 1, str(e))
                    # OCR 失败，保留原有内容（可能为空）

            if content:  # 跳过空白页
                pages.append({
                    "content": content,
                    "page": page_num + 1,
                    "source": source_name,
                    "file_type": "pdf",
                })

        total_pages = len(doc)
        doc.close()
        logger.info(
            "PDF 解析完成: %s, 有效页数: %d/%d, OCR 页数: %d",
            source_name, len(pages), total_pages, ocr_count,
        )

    except fitz.FileDataError:
        raise ValueError(f"无法打开 PDF 文件（可能已损坏）: {file_path}")
    except Exception as e:
        logger.error("PDF 解析异常: %s — %s", source_name, str(e))
        raise

    return pages

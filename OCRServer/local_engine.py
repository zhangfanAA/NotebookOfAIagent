"""
本地 OCR 引擎 — 复用 PaddleOCR 本地能力
OCR 通过子进程执行，避免 PaddlePaddle/OpenCV C++ 内存泄漏
"""

import tempfile
import os
import sys
import subprocess
import json
from pathlib import Path

import fitz  # PyMuPDF

OCR_THRESHOLD = 50
BATCH_SIZE = 10


def ocr_image(image_path: str) -> str:
    """
    对单张图片执行 OCR，返回识别文字。

    Args:
        image_path: 图片文件路径

    Returns:
        识别出的文字
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        result_file = f.name

    try:
        script_path = str(Path(__file__).parent / "ocr_worker.py")
        proc = subprocess.run(
            [sys.executable, script_path, result_file, image_path],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"OCR 子进程失败: {proc.stderr[:200]}")

        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("results", {}).get("0", "")
    finally:
        if os.path.exists(result_file):
            os.unlink(result_file)


def ocr_pdf(pdf_path: str) -> dict:
    """
    解析 PDF，对扫描页执行 OCR，返回文字结果。

    Args:
        pdf_path: PDF 文件路径

    Returns:
        {"pages": [...], "ocr_skipped": False, "ocr_skipped_pages": 0, "ocr_pages": N, "total_pages": M}
    """
    doc = fitz.open(pdf_path)
    source_name = os.path.basename(pdf_path)
    pages = []
    ocr_candidates = []

    # Pass 1: 文字提取
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        lines = [line for line in text.split("\n") if line.strip()]
        cleaned = "\n".join(lines)

        if len(cleaned) < OCR_THRESHOLD:
            ocr_candidates.append(page_num)

        pages.append({
            "content": cleaned,
            "page": page_num + 1,
            "source": source_name,
            "file_type": "pdf",
        })

    doc.close()

    # Pass 2: OCR 扫描页
    ocr_count = 0
    if ocr_candidates:
        for batch_start in range(0, len(ocr_candidates), BATCH_SIZE):
            batch = ocr_candidates[batch_start:batch_start + BATCH_SIZE]
            batch_results = _ocr_pages_batch(pdf_path, batch)
            for page_num, text in batch_results.items():
                pages[page_num]["content"] = text
                ocr_count += 1

    return {
        "pages": pages,
        "ocr_skipped": False,
        "ocr_skipped_pages": 0,
        "ocr_pages": ocr_count,
        "total_pages": len(pages),
    }


def _ocr_pages_batch(pdf_path: str, page_indices: list[int], dpi: int = 200) -> dict[int, str]:
    """批量 OCR 指定页，返回 {page_num: text}"""
    doc = fitz.open(pdf_path)
    temp_images = []

    try:
        for idx in page_indices:
            page = doc[idx]
            pix = page.get_pixmap(dpi=dpi)
            img_path = tempfile.mktemp(suffix=".png")
            pix.save(img_path)
            temp_images.append((idx, img_path))

        doc.close()

        # 调用 OCR 子进程
        result_file = tempfile.mktemp(suffix=".json")
        script_path = str(Path(__file__).parent / "ocr_worker.py")
        image_paths = [img for _, img in temp_images]

        proc = subprocess.run(
            [sys.executable, script_path, result_file] + image_paths,
            capture_output=True, text=True, encoding="utf-8", timeout=300,
        )

        results = {}
        if proc.returncode == 0 and os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("results", {})
            for i, (page_num, _) in enumerate(temp_images):
                text = raw.get(str(i), "")
                lines = [line for line in text.split("\n") if line.strip()]
                results[page_num] = "\n".join(lines)

        if os.path.exists(result_file):
            os.unlink(result_file)

        return results
    finally:
        doc.close() if not doc.is_closed else None
        for _, img_path in temp_images:
            if os.path.exists(img_path):
                os.unlink(img_path)

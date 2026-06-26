"""
智能学习助手 — PDF 文档解析模块
负责: RAG 文档解析

使用 PyMuPDF 提取 PDF 文本，保留页码和元数据。
支持中英文混合文本和代码块。
扫描型 PDF 自动调用 PaddleOCR-VL API 进行 OCR。
"""

import time
from pathlib import Path

import fitz  # PyMuPDF

from src.logger import get_logger

logger = get_logger("data.pdf_parser")

PADDLEOCR_JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
PADDLEOCR_MODEL = "PaddleOCR-VL-1.6"


def _get_ocr_api_key() -> str:
    """从数据库获取余额 OCR API Key"""
    try:
        from src.database.global_config_repo import GlobalConfigRepository
        cfg = GlobalConfigRepository().get_balance_ocr_config()
        return cfg.get("api_key", "")
    except Exception:
        return ""


def _ocr_pdf_with_paddleocr(file_path: str, api_key: str) -> dict:
    """调用 PaddleOCR-VL API 对整个 PDF 进行 OCR"""
    import requests

    headers = {"Authorization": f"bearer {api_key}"}
    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    # 1. 提交任务
    with open(file_path, "rb") as f:
        data = {"model": PADDLEOCR_MODEL, "optionalPayload": __import__("json").dumps(optional_payload)}
        resp = requests.post(PADDLEOCR_JOB_URL, headers=headers, data=data, files={"file": f}, timeout=60)

    if resp.status_code != 200:
        raise RuntimeError(f"OCR API 错误 (HTTP {resp.status_code}): {resp.text[:200]}")

    job_id = resp.json()["data"]["jobId"]
    logger.info("OCR 任务已提交: job=%s", job_id)

    # 2. 轮询结果
    for _ in range(120):
        time.sleep(5)
        job_resp = requests.get(f"{PADDLEOCR_JOB_URL}/{job_id}", headers=headers, timeout=30)
        if job_resp.status_code != 200:
            continue
        job_data = job_resp.json().get("data", {})
        state = job_data.get("state", "")
        if state == "done":
            result_url = job_data.get("resultUrl", {}).get("jsonUrl", "")
            if not result_url:
                raise RuntimeError("OCR 完成但无结果 URL")
            break
        elif state == "failed":
            raise RuntimeError(f"OCR 任务失败: {job_data.get('errorMsg', '未知错误')}")
    else:
        raise RuntimeError("OCR 任务超时（10分钟）")

    # 3. 下载并解析结果
    jsonl_resp = requests.get(result_url, timeout=60)
    jsonl_resp.raise_for_status()

    import json
    pages = []
    for line in jsonl_resp.text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        result = json.loads(line).get("result", {})
        for page in result.get("layoutParsingResults", []):
            md_text = page.get("markdown", {}).get("text", "")
            if md_text.strip():
                pages.append(md_text.strip())

    return {"pages": pages}


def parse_pdf(file_path: str) -> dict:
    """
    解析 PDF 文件，提取每页文本。
    扫描型 PDF（无文字层）自动调用 PaddleOCR-VL 进行 OCR。

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
            "ocr_used": bool,           # 是否使用了 OCR
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
        empty_pages = 0

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
            else:
                empty_pages += 1

        doc.close()
        logger.info("PyMuPDF 解析完成: %s, 有效页: %d, 空白页: %d", source_name, len(pages), empty_pages)

        # 如果超过一半的页面为空，认为是扫描型 PDF，尝试 OCR
        ocr_used = False
        if empty_pages > 0 and empty_pages >= total_pages * 0.5:
            api_key = _get_ocr_api_key()
            if api_key:
                logger.info("检测到扫描型 PDF，启动 PaddleOCR-VL: %s", source_name)
                try:
                    ocr_result = _ocr_pdf_with_paddleocr(file_path, api_key)
                    ocr_pages = ocr_result.get("pages", [])
                    if ocr_pages:
                        pages = []
                        for i, text in enumerate(ocr_pages):
                            pages.append({
                                "content": text,
                                "page": i + 1,
                                "source": source_name,
                                "file_type": "pdf",
                            })
                        ocr_used = True
                        logger.info("OCR 完成: %s, 识别 %d 页", source_name, len(pages))
                    else:
                        logger.warning("OCR 返回空结果: %s", source_name)
                except Exception as e:
                    logger.error("OCR 失败: %s — %s", source_name, str(e))
                    # OCR 失败时保留 PyMuPDF 的结果（可能部分页面有文字）
            else:
                logger.warning("扫描型 PDF 但未配置 OCR API Key: %s", source_name)

    except fitz.FileDataError:
        raise ValueError(f"无法打开 PDF 文件（可能已损坏）: {file_path}")
    except Exception as e:
        logger.error("PDF 解析异常: %s — %s", source_name, str(e))
        raise

    return {
        "pages": pages,
        "ocr_used": ocr_used,
    }

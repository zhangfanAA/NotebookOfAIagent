"""
云端 OCR 客户端 — 调用 PaddleOCR-VL 云端 API
"""

import json
import os
import time
import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"


def ocr_cloud(file_path: str, token: str) -> dict:
    """
    调用云端 OCR API 识别 PDF 或图片。

    Args:
        file_path: 本地文件路径
        token: Bearer token

    Returns:
        与 localPdfOcr 相同格式的结果 dict
    """
    headers = {"Authorization": f"bearer {token}"}
    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    source_name = os.path.basename(file_path)

    # Step 1: 提交任务
    data = {"model": MODEL, "optionalPayload": json.dumps(optional_payload)}
    with open(file_path, "rb") as f:
        files = {"file": f}
        job_response = requests.post(JOB_URL, headers=headers, data=data, files=files, timeout=120)

    if job_response.status_code != 200:
        raise RuntimeError(f"云端 API 返回 {job_response.status_code}: {job_response.text[:200]}")

    job_id = job_response.json()["data"]["jobId"]

    # Step 2: 轮询任务状态
    total_pages = 0
    while True:
        time.sleep(5)
        result_resp = requests.get(f"{JOB_URL}/{job_id}", headers=headers, timeout=30)
        if result_resp.status_code != 200:
            raise RuntimeError(f"轮询失败: HTTP {result_resp.status_code}")

        resp_data = result_resp.json()["data"]
        state = resp_data["state"]

        if state == "pending":
            pass
        elif state == "running":
            progress = resp_data.get("extractProgress", {})
            total_pages = progress.get("totalPages", 0)
        elif state == "done":
            progress = resp_data.get("extractProgress", {})
            total_pages = progress.get("totalPages", 0)
            jsonl_url = resp_data["resultUrl"]["jsonUrl"]
            break
        elif state == "failed":
            error_msg = resp_data.get("errorMsg", "未知错误")
            raise RuntimeError(f"云端 OCR 失败: {error_msg}")

    # Step 3: 下载并解析 JSONL 结果
    jsonl_resp = requests.get(jsonl_url, timeout=120)
    jsonl_resp.raise_for_status()

    pages = []
    for line in jsonl_resp.text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            result = json.loads(line)["result"]
        except (json.JSONDecodeError, KeyError):
            continue
        for res in result.get("layoutParsingResults", []):
            text = res.get("markdown", {}).get("text", "")
            if text.strip():
                pages.append({
                    "content": text.strip(),
                    "page": len(pages) + 1,
                    "source": source_name,
                    "file_type": "pdf",
                })

    ocr_count = len(pages)
    return {
        "pages": pages,
        "ocr_skipped": False,
        "ocr_skipped_pages": 0,
        "ocr_pages": ocr_count,
        "total_pages": max(total_pages, ocr_count),
    }

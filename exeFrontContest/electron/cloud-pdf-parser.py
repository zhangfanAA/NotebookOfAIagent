"""
云端 PDF OCR 脚本 — 由 Electron 主进程通过子进程调用
通过 PaddleOCR 云端 API (paddleocr.aistudio-app.com) 进行文字识别

用法: python cloud-pdf-parser.py <pdf_path> <bearer_token>
输出: JSON 到 stdout
进度: JSON 到 stderr（每行以 [PROGRESS] 开头）

结果格式: 与 local-pdf-parser.py 完全一致
"""

import sys
import json
import os
import io
import time
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"


def report_progress(stage, current=0, total=0, message=""):
    line = json.dumps({
        "stage": stage,
        "current": current,
        "total": total,
        "message": message,
    }, ensure_ascii=False)
    print(f"[PROGRESS]{line}", file=sys.stderr, flush=True)


def parse_pdf_cloud(pdf_path, token):
    headers = {"Authorization": f"bearer {token}"}
    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    source_name = os.path.basename(pdf_path)

    # Step 1: 提交 OCR 任务
    report_progress("uploading", 0, 0, f"正在上传 {source_name} 到云端...")
    data = {"model": MODEL, "optionalPayload": json.dumps(optional_payload)}

    try:
        with open(pdf_path, "rb") as f:
            files = {"file": f}
            job_response = requests.post(
                JOB_URL, headers=headers, data=data, files=files, timeout=120
            )
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": f"上传失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)

    if job_response.status_code != 200:
        error_msg = f"云端 API 返回 {job_response.status_code}: {job_response.text[:200]}"
        print(json.dumps({"error": error_msg}, ensure_ascii=False))
        sys.exit(1)

    job_id = job_response.json()["data"]["jobId"]
    report_progress("processing", 0, 0, f"任务已提交 (ID: {job_id})，等待处理...")

    # Step 2: 轮询任务状态
    total_pages = 0
    while True:
        time.sleep(5)
        try:
            result_resp = requests.get(
                f"{JOB_URL}/{job_id}", headers=headers, timeout=30
            )
        except requests.exceptions.RequestException as e:
            print(json.dumps({"error": f"轮询失败: {str(e)}"}, ensure_ascii=False))
            sys.exit(1)

        if result_resp.status_code != 200:
            print(json.dumps({"error": f"轮询失败: HTTP {result_resp.status_code}"}, ensure_ascii=False))
            sys.exit(1)

        resp_data = result_resp.json()["data"]
        state = resp_data["state"]

        if state == "pending":
            report_progress("processing", 0, 0, "云端排队中...")
        elif state == "running":
            progress = resp_data.get("extractProgress", {})
            total_pages = progress.get("totalPages", 0)
            extracted = progress.get("extractedPages", 0)
            report_progress("ocr", extracted, max(total_pages, 1),
                            f"正在识别: {extracted}/{total_pages} 页")
        elif state == "done":
            progress = resp_data.get("extractProgress", {})
            total_pages = progress.get("totalPages", 0)
            extracted = progress.get("extractedPages", 0)
            report_progress("ocr", extracted, max(total_pages, 1),
                            f"识别完成: {extracted} 页")
            jsonl_url = resp_data["resultUrl"]["jsonUrl"]
            break
        elif state == "failed":
            error_msg = resp_data.get("errorMsg", "未知错误")
            print(json.dumps({"error": f"云端 OCR 失败: {error_msg}"}, ensure_ascii=False))
            sys.exit(1)

    # Step 3: 下载并解析 JSONL 结果
    report_progress("downloading", 0, 0, "正在下载识别结果...")
    try:
        jsonl_resp = requests.get(jsonl_url, timeout=120)
        jsonl_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": f"下载结果失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)

    report_progress("indexing", 0, 0, "正在构建索引...")

    pages = []
    lines = jsonl_resp.text.strip().split('\n')
    for line in lines:
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
    output = {
        "pages": pages,
        "ocr_skipped": False,
        "ocr_skipped_pages": 0,
        "ocr_pages": ocr_count,
        "total_pages": max(total_pages, ocr_count),
    }

    report_progress("done", output["total_pages"], output["total_pages"],
                    f"完成: {ocr_count} 页已识别")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "用法: cloud-pdf-parser.py <pdf_path> <bearer_token>"}))
        sys.exit(1)
    parse_pdf_cloud(sys.argv[1], sys.argv[2])

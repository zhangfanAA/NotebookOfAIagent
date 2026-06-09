"""
本地 PDF 解析 + OCR 脚本 — 由 Electron 主进程通过子进程调用
复制自服务端 pdf_parser.py + _ocr_script.py 的成熟方案

用法: python local-pdf-parser.py <pdf_path>
输出: JSON 到 stdout
进度: JSON 到 stderr（每行以 [PROGRESS] 开头）

结果格式:
{
  "pages": [{"content": "...", "page": 1, "source": "file.pdf", "file_type": "pdf"}],
  "ocr_skipped": false,
  "ocr_skipped_pages": 0,
  "ocr_pages": 3
}
"""

import sys
import json
import os
import io
import tempfile
import subprocess

# 强制 stdout/stderr 使用 UTF-8 编码（Windows 默认 GBK 会报错）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

OCR_THRESHOLD = 50


def report_progress(stage, current=0, total=0, message=""):
    """输出进度到 stderr，Electron 主进程解析后转发给渲染进程"""
    line = json.dumps({
        "stage": stage,
        "current": current,
        "total": total,
        "message": message,
    }, ensure_ascii=False)
    print(f"[PROGRESS]{line}", file=sys.stderr, flush=True)


def ocr_images_batch(image_paths):
    """通过子进程批量 OCR 图片（子进程退出后内存完全释放）"""
    if not image_paths:
        return {}

    result_file = tempfile.mktemp(suffix=".json")
    ocr_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local-ocr-batch.py")

    try:
        proc = subprocess.run(
            [sys.executable, ocr_script, result_file] + image_paths,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0 and os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("results", {})
    except Exception:
        pass
    finally:
        if os.path.exists(result_file):
            os.unlink(result_file)

    return {}


def parse_pdf(pdf_path):
    """解析 PDF，对扫描页自动 OCR"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(json.dumps({"error": "PyMuPDF 未安装，请运行: pip install pymupdf"}))
        sys.exit(1)

    if not os.path.exists(pdf_path):
        print(json.dumps({"error": f"文件不存在: {pdf_path}"}))
        sys.exit(1)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(json.dumps({"error": f"无法打开 PDF: {str(e)}"}))
        sys.exit(1)

    total_pages = len(doc)
    source_name = os.path.basename(pdf_path)

    report_progress("parsing", 0, total_pages, f"开始解析: {source_name} ({total_pages} 页)")

    # 第一轮：提取文本，标记 OCR 候选页
    raw_texts = []
    ocr_candidates = []

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

        if len(content) < OCR_THRESHOLD:
            ocr_candidates.append(page_num)

        raw_texts.append((page_num, content))

    report_progress("parsed", total_pages, total_pages,
                    f"文本提取完成: {len(ocr_candidates)} 页需要 OCR")

    # 第二轮：批量 OCR 扫描页
    ocr_results = {}
    if ocr_candidates:
        BATCH_SIZE = 10
        total_batches = (len(ocr_candidates) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_start in range(0, len(ocr_candidates), BATCH_SIZE):
            batch_indices = ocr_candidates[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1

            report_progress("ocr", batch_start, len(ocr_candidates),
                            f"OCR 批次 {batch_num}/{total_batches}: 正在识别 {len(batch_indices)} 页...")

            # 提取页面为临时图片
            temp_images = []
            for page_num in batch_indices:
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
                os.close(tmp_fd)
                pix.save(tmp_path)
                del pix
                temp_images.append(tmp_path)

            # 子进程 OCR
            batch_results = ocr_images_batch(temp_images)

            # 收集结果
            success = 0
            for i, page_num in enumerate(batch_indices):
                text = batch_results.get(str(i), "")
                if text.strip():
                    ocr_results[page_num] = text.strip()
                    success += 1

            # 清理临时图片
            for img_path in temp_images:
                if os.path.exists(img_path):
                    os.unlink(img_path)

            report_progress("ocr", batch_start + len(batch_indices), len(ocr_candidates),
                            f"OCR 批次 {batch_num}/{total_batches} 完成: {success}/{len(batch_indices)} 页成功")

    doc.close()

    report_progress("indexing", 0, 0, "正在构建索引...")

    # 合并结果
    pages = []
    for page_num, content in raw_texts:
        if page_num in ocr_results:
            content = ocr_results[page_num]
        if content:
            pages.append({
                "content": content,
                "page": page_num + 1,
                "source": source_name,
                "file_type": "pdf",
            })

    ocr_skipped_count = 0

    result = {
        "pages": pages,
        "ocr_skipped": ocr_skipped_count > 0,
        "ocr_skipped_pages": ocr_skipped_count,
        "ocr_pages": len(ocr_results),
        "total_pages": total_pages,
    }

    report_progress("done", total_pages, total_pages,
                    f"完成: {len(pages)}/{total_pages} 页有效, OCR 识别 {len(ocr_results)} 页")

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "未指定 PDF 路径"}))
        sys.exit(1)
    parse_pdf(sys.argv[1])

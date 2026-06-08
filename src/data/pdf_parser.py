"""
智能学习助手 — PDF 文档解析模块
负责: RAG
任务: TASK-DATA-002

使用 PyMuPDF 提取 PDF 文本，保留页码和元数据。
支持中英文混合文本和代码块。
支持扫描型 PDF 自动 OCR（PaddleOCR，可通过管理员开关控制，自动检测 GPU）。

OCR 使用子进程执行：PaddlePaddle/OpenCV 的 C++ 内存无法由 Python GC 回收，
子进程退出时操作系统自动回收全部内存，避免主进程内存持续膨胀。
"""

import tempfile
import os
import sys
import subprocess
import json
from pathlib import Path

import fitz  # PyMuPDF

from src.logger import get_logger

logger = get_logger("data.pdf_parser")

# 扫描页判定阈值：文字少于此数时触发 OCR
OCR_THRESHOLD = 50

_gpu_available = None


def _is_paddle_ocr_enabled() -> bool:
    """检查 PaddleOCR 是否启用"""
    try:
        from src.database.global_config_repo import GlobalConfigRepository
        return GlobalConfigRepository().get_paddle_ocr_enabled()
    except Exception:
        return True


def _check_gpu_available() -> bool:
    """
    检测 PaddlePaddle 是否能实际使用 GPU

    Returns:
        True 如果 PaddlePaddle 可以使用 GPU，否则 False
    """
    global _gpu_available
    if _gpu_available is not None:
        return _gpu_available

    try:
        import paddle
        if not paddle.device.is_compiled_with_cuda():
            logger.info("PaddlePaddle 未编译 CUDA 支持（CPU 版本），将使用 CPU 模式")
            _gpu_available = False
            return False

        try:
            gpu_count = paddle.device.cuda.device_count()
            if gpu_count > 0:
                gpu_name = paddle.device.cuda.get_device_name(0)
                logger.info("PaddlePaddle GPU 可用: %s (共 %d 个 GPU)", gpu_name, gpu_count)
                _gpu_available = True
                return True
        except Exception as e:
            logger.warning("检测 GPU 设备失败: %s", str(e))

    except ImportError:
        logger.warning("PaddlePaddle 未安装")

    logger.info("PaddlePaddle GPU 不可用，将使用 CPU 模式")
    _gpu_available = False
    return False


def get_device_info() -> dict:
    """
    获取当前 OCR 设备信息

    Returns:
        {"gpu_available": bool, "device": str, "details": str}
    """
    gpu_available = _check_gpu_available()

    if gpu_available:
        try:
            import paddle
            gpu_name = paddle.device.cuda.get_device_name(0)
            return {
                "gpu_available": True,
                "device": "GPU",
                "details": gpu_name,
            }
        except Exception:
            pass

    return {
        "gpu_available": False,
        "device": "CPU",
        "details": "PaddlePaddle CPU 版本",
    }


# ===== 子进程 OCR =====

_OCR_SCRIPT = os.path.join(os.path.dirname(__file__), "_ocr_script.py")


def _ocr_pages_batch(pdf_path: str, page_indices: list, dpi: int = 200) -> dict:
    """
    通过独立子进程批量 OCR 指定页面（进程退出后内存完全释放）

    Args:
        pdf_path: PDF 文件路径
        page_indices: 需要 OCR 的页码列表（0-based）
        dpi: 图片分辨率

    Returns:
        {page_num: ocr_text}
    """
    if not page_indices:
        return {}

    # 分批 OCR（每批最多 10 页），避免主进程一次性提取过多图片导致内存暴涨
    BATCH_SIZE = 10
    all_results = {}
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")

    for batch_start in range(0, len(page_indices), BATCH_SIZE):
        batch_indices = page_indices[batch_start:batch_start + BATCH_SIZE]

        # 1. 提取当前批次页面为临时图片
        doc = fitz.open(pdf_path)
        temp_images = []
        for page_num in batch_indices:
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(tmp_fd)
            pix.save(tmp_path)
            del pix  # 立即释放像素数据
            temp_images.append(tmp_path)
        doc.close()

        # 2. 子进程执行 OCR
        result_file = tempfile.mktemp(suffix=".json")
        ocr_data = {}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "src.data._ocr_script", result_file] + temp_images,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=project_root,
            )
            if proc.stderr:
                for line in proc.stderr.strip().split("\n"):
                    if "[OCR_SCRIPT]" in line:
                        logger.info("子进程: %s", line.strip())

            if proc.returncode != 0:
                logger.error("子进程 OCR 失败: %s", proc.stderr[:500])
            elif os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    ocr_data = json.load(f)
            else:
                logger.error("子进程 OCR 未生成结果文件")
        except subprocess.TimeoutExpired:
            logger.error("子进程 OCR 超时")
        except json.JSONDecodeError as e:
            logger.error("子进程 OCR 结果解析失败: %s", str(e))
        except Exception as e:
            logger.error("子进程 OCR 异常: %s", str(e))
        finally:
            if os.path.exists(result_file):
                os.unlink(result_file)

        # 3. 清理临时图片
        for img_path in temp_images:
            if os.path.exists(img_path):
                os.unlink(img_path)

        # 4. 收集当前批次结果
        results_map = ocr_data.get("results", {})
        for i, page_num in enumerate(batch_indices):
            text = results_map.get(str(i), "")
            if text.strip():
                all_results[page_num] = text.strip()

        logger.info("OCR 批次 %d-%d 完成: %d/%d 页成功",
                     batch_start + 1, min(batch_start + BATCH_SIZE, len(page_indices)),
                     len([v for v in all_results.values() if v]), len(batch_indices))

    return all_results


def parse_pdf(file_path: str) -> dict:
    """
    解析 PDF 文件，提取每页文本

    自动检测扫描型页面并使用 OCR 识别（需管理员启用 PaddleOCR）。
    OCR 在子进程中执行，完成后子进程退出，内存自动释放。

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
            "ocr_skipped": bool,        # 是否有扫描页因 OCR 关闭而跳过
            "ocr_skipped_pages": int,   # 跳过的扫描页数量
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
    paddle_enabled = _is_paddle_ocr_enabled()

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info("开始解析 PDF: %s (%d 页), PaddleOCR: %s", source_name, total_pages, "启用" if paddle_enabled else "禁用")

        # 第一轮：提取所有页面文本，标记需要 OCR 的页面
        raw_texts = []       # [(page_num, text)]
        ocr_candidates = []  # [page_num] 需要 OCR 的页码

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

            if len(content) < OCR_THRESHOLD and paddle_enabled:
                ocr_candidates.append(page_num)
                logger.info("第 %d 页文字过少(%d字)，标记为 OCR 候选", page_num + 1, len(content))

            raw_texts.append((page_num, content))

        doc.close()

        # 第二轮：子进程批量 OCR
        ocr_results = {}
        ocr_count = 0
        ocr_skipped_count = 0

        if ocr_candidates:
            logger.info("启动子进程 OCR: %d 页需要识别", len(ocr_candidates))
            ocr_results = _ocr_pages_batch(file_path, ocr_candidates)
            ocr_count = len(ocr_results)
            logger.info("子进程 OCR 完成: %d/%d 页成功，子进程内存已释放", ocr_count, len(ocr_candidates))
        elif not paddle_enabled:
            ocr_skipped_count = sum(1 for _, text in raw_texts if len(text) < OCR_THRESHOLD)

        # 合并结果
        pages = []
        for page_num, content in raw_texts:
            # 如果该页有 OCR 结果，替换原文
            if page_num in ocr_results:
                content = ocr_results[page_num]

            if content:
                pages.append({
                    "content": content,
                    "page": page_num + 1,
                    "source": source_name,
                    "file_type": "pdf",
                })

        logger.info(
            "PDF 解析完成: %s, 有效页数: %d/%d, OCR 页数: %d, 跳过扫描页: %d",
            source_name, len(pages), total_pages, ocr_count, ocr_skipped_count,
        )

    except fitz.FileDataError:
        raise ValueError(f"无法打开 PDF 文件（可能已损坏）: {file_path}")
    except Exception as e:
        logger.error("PDF 解析异常: %s — %s", source_name, str(e))
        raise

    return {
        "pages": pages,
        "ocr_skipped": ocr_skipped_count > 0,
        "ocr_skipped_pages": ocr_skipped_count,
    }

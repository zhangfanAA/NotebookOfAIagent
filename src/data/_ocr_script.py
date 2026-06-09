"""
独立 OCR 脚本（由 pdf_parser.py 通过 subprocess 调用）

用法: python -m src.data._ocr_script <result_file> <image_path1> <image_path2> ...

结果写入 result_file（JSON 格式）: {"results": {"0": "文字", "1": "文字", ...}}

此脚本在独立进程中运行，退出后操作系统回收全部 PaddlePaddle/OpenCV 内存。
"""

import sys
import json
import os


def main():
    if len(sys.argv) < 3:
        return

    result_file = sys.argv[1]
    image_paths = sys.argv[2:]

    # 写调试信息到 stderr
    debug = lambda msg: sys.stderr.write(f"[OCR_SCRIPT] {msg}\n")

    debug(f"Starting: {len(image_paths)} images, result_file={result_file}")

    import paddle
    from paddleocr import PaddleOCR

    debug(f"PaddlePaddle version={paddle.__version__}, CUDA compiled={paddle.device.is_compiled_with_cuda()}")
    # 强制 CPU 模式（避免 cuDNN 缺失导致崩溃）
    ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False, use_gpu=False)
    debug("PaddleOCR initialized")

    results = {}
    for i, img_path in enumerate(image_paths):
        try:
            if not os.path.exists(img_path):
                debug(f"Image {i} NOT FOUND: {img_path}")
                results[str(i)] = ""
                continue
            debug(f"Processing image {i}: {img_path}")
            result = ocr.ocr(img_path, cls=True)
            lines = []
            if result and result[0]:
                for line_info in result[0]:
                    text = line_info[1][0]
                    lines.append(text)
            results[str(i)] = "\n".join(lines)
            debug(f"Image {i}: {len(lines)} lines")
        except Exception as e:
            debug(f"Image {i} ERROR: {e}")
            results[str(i)] = ""

    debug(f"Writing results: {len(results)} entries")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False)
    debug("Done")


if __name__ == "__main__":
    main()

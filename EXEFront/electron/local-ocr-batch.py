"""
批量 OCR 脚本 — 由 local-pdf-parser.py 通过子进程调用
复制自服务端 src/data/_ocr_script.py

用法: python local-ocr-batch.py <result_file> <image1> <image2> ...
输出: 写入 result_file JSON 格式 {"results": {"0": "文字", "1": "文字", ...}}

此脚本在独立进程中运行，退出后操作系统回收全部 PaddlePaddle/OpenCV 内存。
"""

import sys
import json
import os
import io

# 强制 stdout/stderr 使用 UTF-8 编码（Windows 默认 GBK 会报错）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    if len(sys.argv) < 3:
        return

    result_file = sys.argv[1]
    image_paths = sys.argv[2:]

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({"results": {}, "error": "PaddleOCR 未安装"}, f)
        return

    ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False, use_gpu=False)

    results = {}
    for i, img_path in enumerate(image_paths):
        try:
            if not os.path.exists(img_path):
                results[str(i)] = ""
                continue
            result = ocr.ocr(img_path, cls=True)
            lines = []
            if result and result[0]:
                for line_info in result[0]:
                    if line_info and len(line_info) >= 2:
                        text = line_info[1][0]
                        lines.append(text)
            results[str(i)] = "\n".join(lines)
        except Exception:
            results[str(i)] = ""

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()

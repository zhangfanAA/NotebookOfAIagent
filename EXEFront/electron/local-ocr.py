"""
本地 OCR 脚本 — 由 Electron 主进程通过子进程调用
用法: python local-ocr.py <image_path>
输出: JSON 到 stdout
"""

import sys
import json
import os
import io

# 强制 stdout 使用 UTF-8 编码（Windows 默认 GBK 会报错）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "未指定图片路径"}))
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(json.dumps({"error": f"文件不存在: {image_path}"}))
        sys.exit(1)

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print(json.dumps({"error": "PaddleOCR 未安装，请运行: pip install paddleocr paddlepaddle"}))
        sys.exit(1)

    try:
        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False, use_gpu=False)
        result = ocr.ocr(image_path, cls=True)

        lines = []
        if result and result[0]:
            for line_info in result[0]:
                if line_info and len(line_info) >= 2:
                    text = line_info[1][0]
                    confidence = line_info[1][1]
                    lines.append({"text": text, "confidence": confidence})

        full_text = "\n".join(line["text"] for line in lines)
        print(json.dumps({
            "text": full_text,
            "lines": len(lines),
            "details": lines,
        }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": f"OCR 执行失败: {str(e)}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()

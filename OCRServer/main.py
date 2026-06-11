"""
OCR 服务器 — 独立 FastAPI 应用
接收图片或 PDF，返回识别文字

启动: python main.py
端口: 环境变量 OCR_PORT (默认 8001)
模式: 环境变量 OCR_MODE (cloud/local，默认 cloud)
"""

import os
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OCR 服务器", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OCR_MODE = os.environ.get("OCR_MODE", "cloud")


@app.get("/ocr/health")
async def health():
    return {"status": "ok", "mode": OCR_MODE}


@app.post("/ocr/image")
async def ocr_image_endpoint(
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    """接收图片文件，返回识别文字"""
    suffix = _get_suffix(file.filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if OCR_MODE == "cloud":
            token = _extract_token(authorization)
            if not token:
                raise HTTPException(400, "云端模式需要提供 Authorization Bearer Token")
            from cloud_client import ocr_cloud
            result = ocr_cloud(tmp_path, token)
        else:
            from local_engine import ocr_image
            text = ocr_image(tmp_path)
            result = {"text": text}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"OCR 处理失败: {str(e)}")
    finally:
        os.unlink(tmp_path)


@app.post("/ocr/pdf")
async def ocr_pdf_endpoint(
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
):
    """接收 PDF 文件，返回识别文字"""
    suffix = _get_suffix(file.filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if OCR_MODE == "cloud":
            token = _extract_token(authorization)
            if not token:
                raise HTTPException(400, "云端模式需要提供 Authorization Bearer Token")
            from cloud_client import ocr_cloud
            result = ocr_cloud(tmp_path, token)
        else:
            from local_engine import ocr_pdf
            result = ocr_pdf(tmp_path)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"OCR 处理失败: {str(e)}")
    finally:
        os.unlink(tmp_path)


def _get_suffix(filename: str | None) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1]
    return ".pdf"


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:]
    return authorization


if __name__ == "__main__":
    port = int(os.environ.get("OCR_PORT", "8001"))
    print(f"OCR 服务器启动中... 模式={OCR_MODE}, 端口={port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

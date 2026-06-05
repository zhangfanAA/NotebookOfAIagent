import os
import sys
import time
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.rag.rag_service import RAGService
from src.config import get_config
from src.logger import get_logger

logger = get_logger("api.routes")

app = FastAPI(title="智能学习助手 API", version="0.2.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 安全配置 =====

# API Key 认证（可选，通过环境变量启用）
API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# 速率限制配置
RATE_LIMIT_WINDOW = 60  # 秒
RATE_LIMIT_MAX_REQUESTS = 30  # 每窗口最大请求数
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# 速率限制存储
_rate_limit_store = defaultdict(list)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """验证 API Key（如果配置了的话）"""
    if API_KEY and api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


def check_rate_limit(client_ip: str):
    """检查速率限制"""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # 清理过期记录
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    _rate_limit_store[client_ip].append(now)


# ===== 服务实例 =====

_rag_service = None


def get_rag():
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


# ===== 请求模型 =====

class ChatRequest(BaseModel):
    question: str
    session_id: str


class SessionCreateRequest(BaseModel):
    title: str = "New Session"


class RenameRequest(BaseModel):
    title: str


# ===== 路由 =====

@app.get("/api/status")
async def health_check():
    """健康检查（无需认证）"""
    rag = get_rag()
    stats = rag.get_vector_db_stats()
    return {"status": "ok", "version": "0.2.0", "vector_db": stats}


@app.post("/api/chat")
async def chat(request: Request, body: ChatRequest, _: bool = Depends(verify_api_key)):
    """发送消息（需要认证）"""
    check_rate_limit(request.client.host)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    rag = get_rag()
    result = rag.query(body.question, body.session_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/api/upload")
async def upload_document(request: Request, file: UploadFile = File(...), _: bool = Depends(verify_api_key)):
    """上传文档（需要认证）"""
    check_rate_limit(request.client.host)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制（最大 50MB）")

    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        rag = get_rag()
        result = rag.upload_document(tmp_path)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    finally:
        os.unlink(tmp_path)


@app.post("/api/sessions")
async def create_session(request: Request, body: SessionCreateRequest, _: bool = Depends(verify_api_key)):
    """创建会话"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    session_id = rag.create_session(body.title)
    return {"session_id": session_id, "title": body.title}


@app.get("/api/sessions")
async def list_sessions(_: bool = Depends(verify_api_key)):
    """获取会话列表"""
    rag = get_rag()
    return {"sessions": rag.get_sessions()}


@app.get("/api/sessions/{sid}")
async def get_session_history(sid: str, _: bool = Depends(verify_api_key)):
    """获取会话历史"""
    rag = get_rag()
    messages = rag.get_session_history(sid)
    return {"session_id": sid, "messages": messages}


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str, _: bool = Depends(verify_api_key)):
    """删除会话"""
    rag = get_rag()
    success = rag.delete_session(sid)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": sid}


@app.patch("/api/sessions/{sid}")
async def rename_session(sid: str, request: Request, body: RenameRequest, _: bool = Depends(verify_api_key)):
    """重命名会话"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.update_session_title(sid, body.title.strip())
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "renamed", "session_id": sid, "title": body.title.strip()}


@app.get("/api/sessions/{sid}/summary")
async def get_session_summary(sid: str, _: bool = Depends(verify_api_key)):
    """获取会话摘要"""
    rag = get_rag()
    summary = rag.get_conversation_summary(sid)
    return {"session_id": sid, **summary}


@app.get("/api/sessions/{sid}/topics")
async def get_session_topics(sid: str, _: bool = Depends(verify_api_key)):
    """获取会话话题"""
    rag = get_rag()
    topics = rag.get_recent_topics(sid)
    return {"session_id": sid, "topics": topics}


@app.get("/api/sessions/{sid}/diagnosis")
async def get_diagnosis(sid: str, _: bool = Depends(verify_api_key)):
    """获取学习诊断"""
    rag = get_rag()
    weak_topics = rag.get_weak_topics(sid)
    return {"session_id": sid, "weak_topics": weak_topics}


@app.get("/api/documents")
async def list_documents(status: str = None, limit: int = 50, _: bool = Depends(verify_api_key)):
    """获取文档列表"""
    rag = get_rag()
    documents = rag.get_documents()
    return {"documents": documents}


@app.get("/api/diagnostics")
async def system_diagnostics(_: bool = Depends(verify_api_key)):
    """系统诊断"""
    from src.utils.startup_check import run_startup_checks
    checks = run_startup_checks()
    rag = get_rag()
    stats = rag.get_vector_db_stats()
    return {"startup_checks": checks, "vector_db_stats": stats}

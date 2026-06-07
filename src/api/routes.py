import os
import sys
import json
import time
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.rag.rag_service import RAGService
from src.config import get_config
from src.logger import get_logger

logger = get_logger("api.routes")

app = FastAPI(title="智能学习助手 API", version="0.2.0")


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("未捕获异常: %s %s — %s", request.method, request.url.path, str(exc))
    return HTTPException(status_code=500, detail=f"服务器内部错误: {str(exc)[:200]}")


# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 安全配置 =====

# JWT 认证
security = HTTPBearer(auto_error=False)

# 速率限制配置
RATE_LIMIT_WINDOW = 60  # 秒
RATE_LIMIT_MAX_REQUESTS = 30  # 每窗口最大请求数
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# 速率限制存储
_rate_limit_store = defaultdict(list)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """从 JWT token 获取当前用户"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        from src.api.auth import verify_token
        payload = verify_token(credentials.credentials)
        return {"user_id": payload["user_id"], "username": payload["username"]}
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


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

class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    question: str
    session_id: str


class SessionCreateRequest(BaseModel):
    title: str = "New Session"


class RenameRequest(BaseModel):
    title: str


class GenerateRequest(BaseModel):
    file_names: list
    user_prompt: str = ""
    output_type: str = "mindmap"


class SaveMindmapRequest(BaseModel):
    title: str
    output_type: str = "mindmap"
    content: str
    mermaid_code: str = None
    file_names: list = []


class QuizRequest(BaseModel):
    file_names: list
    num_questions: int = 5
    difficulty: str = "medium"
    qtypes: list = ["choice", "fill", "short_answer"]


class QuizCheckRequest(BaseModel):
    question: dict
    user_answer: str


class FlashcardRequest(BaseModel):
    file_names: list
    num_cards: int = 10
    topic_focus: str = ""


class SaveQuizRequest(BaseModel):
    title: str
    questions: list
    score_correct: int = 0
    score_total: int = 0
    difficulty: str = "medium"
    file_names: list = []


class SaveFlashcardRequest(BaseModel):
    title: str
    cards: list
    file_names: list = []


class CompareRequest(BaseModel):
    file_names: list
    focus: str = ""


class ReadingProgressRequest(BaseModel):
    file_name: str
    current_page: int
    total_pages: int = 0


class BookmarkRequest(BaseModel):
    file_name: str
    page_number: int
    title: str = None
    note: str = None


class TagRequest(BaseModel):
    name: str
    color: str = "#5ac8fa"


class MessageTagRequest(BaseModel):
    message_id: int
    tag_id: int


class NotesRequest(BaseModel):
    notes: str


class FavoriteRequest(BaseModel):
    content: str
    question: str = None


class SearchRequest(BaseModel):
    keyword: str


class LlmSettingsRequest(BaseModel):
    provider: str  # "local" or "cloud"
    cloud_base_url: str = ""
    cloud_api_key: str = ""
    cloud_model: str = ""


# ===== 路由 =====

@app.get("/api/status")
async def health_check():
    """健康检查（无需认证）"""
    rag = get_rag()
    stats = rag.get_vector_db_stats()
    return {"status": "ok", "version": "0.2.0", "vector_db": stats}


@app.get("/api/rate-limit")
async def rate_limit_info(request: Request):
    """查询当前 IP 的限流状态（无需认证）"""
    client_ip = request.client.host
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    recent = [t for t in _rate_limit_store.get(client_ip, []) if t > window_start]
    remaining = max(0, RATE_LIMIT_MAX_REQUESTS - len(recent))
    return {
        "limit": RATE_LIMIT_MAX_REQUESTS,
        "window_seconds": RATE_LIMIT_WINDOW,
        "remaining": remaining,
        "used": len(recent),
    }


@app.post("/api/auth/login")
async def login(body: LoginRequest, request: Request):
    """用户登录"""
    check_rate_limit(request.client.host)
    from src.api.auth import authenticate_user, create_token
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["id"], user["username"])
    return {"token": token, "username": user["username"]}


@app.post("/api/chat")
async def chat(request: Request, body: ChatRequest, user = Depends(get_current_user)):
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
async def upload_document(request: Request, file: UploadFile = File(...), user = Depends(get_current_user)):
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
        result = rag.upload_document(tmp_path, original_filename=file.filename, user_id=user["user_id"])
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    finally:
        os.unlink(tmp_path)


@app.post("/api/sessions")
async def create_session(request: Request, body: SessionCreateRequest, user = Depends(get_current_user)):
    """创建会话"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    session_id = rag.create_session(body.title, user_id=user["user_id"])
    return {"session_id": session_id, "title": body.title}


@app.get("/api/sessions")
async def list_sessions(page: int = 1, page_size: int = 20, user = Depends(get_current_user)):
    """获取会话列表（支持分页）"""
    rag = get_rag()
    sessions = rag.get_sessions(user_id=user["user_id"])
    # 简单内存分页
    total = len(sessions)
    start = (page - 1) * page_size
    end = start + page_size
    paged = sessions[start:end]
    return {"sessions": paged, "total": total, "page": page, "page_size": page_size}


@app.get("/api/sessions/{sid}")
async def get_session_history(sid: str, user = Depends(get_current_user)):
    """获取会话历史"""
    rag = get_rag()
    messages = rag.get_session_history(sid)
    return {"session_id": sid, "messages": messages}


@app.delete("/api/sessions/{sid}")
async def delete_session(sid: str, user = Depends(get_current_user)):
    """删除会话"""
    rag = get_rag()
    success = rag.delete_session(sid)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": sid}


@app.patch("/api/sessions/{sid}")
async def rename_session(sid: str, request: Request, body: RenameRequest, user = Depends(get_current_user)):
    """重命名会话"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.update_session_title(sid, body.title.strip())
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "renamed", "session_id": sid, "title": body.title.strip()}


@app.get("/api/sessions/{sid}/summary")
async def get_session_summary(sid: str, user = Depends(get_current_user)):
    """获取会话摘要"""
    rag = get_rag()
    summary = rag.get_conversation_summary(sid)
    return {"session_id": sid, **summary}


@app.get("/api/sessions/{sid}/topics")
async def get_session_topics(sid: str, user = Depends(get_current_user)):
    """获取会话话题"""
    rag = get_rag()
    topics = rag.get_recent_topics(sid)
    return {"session_id": sid, "topics": topics}


@app.get("/api/sessions/{sid}/diagnosis")
async def get_diagnosis(sid: str, user = Depends(get_current_user)):
    """获取学习诊断"""
    rag = get_rag()
    weak_topics = rag.get_weak_topics(sid)
    return {"session_id": sid, "weak_topics": weak_topics}


@app.get("/api/documents")
async def list_documents(status: str = None, limit: int = 50, user = Depends(get_current_user)):
    """获取文档列表"""
    rag = get_rag()
    documents = rag.get_documents(user_id=user["user_id"])
    return {"documents": documents}


@app.get("/api/diagnostics")
async def system_diagnostics(user = Depends(get_current_user)):
    """系统诊断"""
    from src.utils.startup_check import run_startup_checks
    checks = run_startup_checks()
    rag = get_rag()
    stats = rag.get_vector_db_stats()
    return {"startup_checks": checks, "vector_db_stats": stats}


@app.post("/api/generate")
async def generate_content(request: Request, body: GenerateRequest, user = Depends(get_current_user)):
    """生成思维导图或重点笔记"""
    check_rate_limit(request.client.host)
    if not body.file_names:
        raise HTTPException(status_code=400, detail="请至少选择一个文件")
    if body.output_type not in ("mindmap", "notes"):
        raise HTTPException(status_code=400, detail="output_type 必须为 mindmap 或 notes")
    rag = get_rag()
    result = rag.generate_content(body.file_names, body.user_prompt, body.output_type)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/api/mindmaps")
async def save_mindmap(body: SaveMindmapRequest, user = Depends(get_current_user)):
    """保存思维导图/笔记"""
    from src.database.mindmap_repo import MindmapRepository
    repo = MindmapRepository()
    mindmap_id = repo.save(body.title, body.output_type, body.content, body.mermaid_code, body.file_names, user_id=user["user_id"])
    return {"status": "saved", "id": mindmap_id}


@app.get("/api/mindmaps")
async def list_mindmaps(type: str = None, user = Depends(get_current_user)):
    """列出已保存的思维导图/笔记"""
    from src.database.mindmap_repo import MindmapRepository
    repo = MindmapRepository()
    return {"items": repo.list(output_type=type, user_id=user["user_id"])}


@app.get("/api/mindmaps/{mindmap_id}")
async def get_mindmap(mindmap_id: int, user = Depends(get_current_user)):
    """获取单个思维导图/笔记详情"""
    from src.database.mindmap_repo import MindmapRepository
    repo = MindmapRepository()
    result = repo.get(mindmap_id)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


@app.delete("/api/mindmaps/{mindmap_id}")
async def delete_mindmap(mindmap_id: int, user = Depends(get_current_user)):
    """删除已保存的思维导图/笔记"""
    from src.database.mindmap_repo import MindmapRepository
    repo = MindmapRepository()
    success = repo.delete(mindmap_id)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"status": "deleted", "id": mindmap_id}


@app.post("/api/quiz")
async def generate_quiz(request: Request, body: QuizRequest, user = Depends(get_current_user)):
    """生成测验题目"""
    check_rate_limit(request.client.host)
    if not body.file_names:
        raise HTTPException(status_code=400, detail="请至少选择一个文件")
    rag = get_rag()
    result = rag.generate_quiz(body.file_names, body.num_questions, body.difficulty, body.qtypes)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/api/quiz/check")
async def check_quiz_answer(request: Request, body: QuizCheckRequest, user = Depends(get_current_user)):
    """判分"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    result = rag.check_quiz_answer(body.question, body.user_answer)
    return result


@app.post("/api/quizzes")
async def save_quiz(body: SaveQuizRequest, user = Depends(get_current_user)):
    """保存测验"""
    from src.database.quiz_repo import QuizRepository
    repo = QuizRepository()
    quiz_id = repo.save(body.title, body.questions, body.score_correct, body.score_total, body.difficulty, body.file_names, user_id=user["user_id"])
    return {"status": "saved", "id": quiz_id}


@app.get("/api/quizzes")
async def list_quizzes(user = Depends(get_current_user)):
    """列出已保存的测验"""
    from src.database.quiz_repo import QuizRepository
    repo = QuizRepository()
    return {"items": repo.list(user_id=user["user_id"])}


@app.get("/api/quizzes/{quiz_id}")
async def get_quiz(quiz_id: int, user = Depends(get_current_user)):
    """获取单个测验详情"""
    from src.database.quiz_repo import QuizRepository
    repo = QuizRepository()
    result = repo.get(quiz_id)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


@app.delete("/api/quizzes/{quiz_id}")
async def delete_quiz(quiz_id: int, user = Depends(get_current_user)):
    """删除已保存的测验"""
    from src.database.quiz_repo import QuizRepository
    repo = QuizRepository()
    success = repo.delete(quiz_id)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"status": "deleted", "id": quiz_id}


@app.post("/api/flashcards")
async def generate_flashcards(request: Request, body: FlashcardRequest, user = Depends(get_current_user)):
    """生成闪卡"""
    check_rate_limit(request.client.host)
    if not body.file_names:
        raise HTTPException(status_code=400, detail="请至少选择一个文件")
    rag = get_rag()
    result = rag.generate_flashcards(body.file_names, body.num_cards, body.topic_focus)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/api/flashcards/save")
async def save_flashcard_set(body: SaveFlashcardRequest, user = Depends(get_current_user)):
    """保存闪卡集"""
    from src.database.flashcard_repo import FlashcardRepository
    repo = FlashcardRepository()
    fc_id = repo.save(body.title, body.cards, body.file_names, user_id=user["user_id"])
    return {"status": "saved", "id": fc_id}


@app.get("/api/flashcards/saved")
async def list_flashcard_sets(user = Depends(get_current_user)):
    """列出已保存的闪卡集"""
    from src.database.flashcard_repo import FlashcardRepository
    repo = FlashcardRepository()
    return {"items": repo.list(user_id=user["user_id"])}


@app.get("/api/flashcards/saved/{fc_id}")
async def get_flashcard_set(fc_id: int, user = Depends(get_current_user)):
    """获取单个闪卡集详情"""
    from src.database.flashcard_repo import FlashcardRepository
    repo = FlashcardRepository()
    result = repo.get(fc_id)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


@app.delete("/api/flashcards/saved/{fc_id}")
async def delete_flashcard_set(fc_id: int, user = Depends(get_current_user)):
    """删除已保存的闪卡集"""
    from src.database.flashcard_repo import FlashcardRepository
    repo = FlashcardRepository()
    success = repo.delete(fc_id)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"status": "deleted", "id": fc_id}


@app.post("/api/compare")
async def compare_documents(request: Request, body: CompareRequest, user = Depends(get_current_user)):
    """文档对比"""
    check_rate_limit(request.client.host)
    if len(body.file_names) < 2:
        raise HTTPException(status_code=400, detail="请至少选择两个文件")
    rag = get_rag()
    result = rag.compare_documents(body.file_names, body.focus)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


# ===== 阅读进度 =====

@app.post("/api/reading-progress")
async def update_reading_progress(request: Request, body: ReadingProgressRequest, user = Depends(get_current_user)):
    """更新阅读进度"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.update_reading_progress(body.file_name, body.current_page, body.total_pages, user_id=user["user_id"])
    return {"status": "ok" if success else "error"}


@app.get("/api/reading-progress")
async def get_reading_progress(user = Depends(get_current_user)):
    """获取所有阅读进度"""
    rag = get_rag()
    return {"progress": rag.get_all_reading_progress(user_id=user["user_id"])}


# ===== 书签 =====

@app.post("/api/bookmarks")
async def add_bookmark(request: Request, body: BookmarkRequest, user = Depends(get_current_user)):
    """添加书签"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    bookmark_id = rag.add_bookmark(body.file_name, body.page_number, body.title, body.note, user_id=user["user_id"])
    return {"id": bookmark_id, "status": "ok"}


@app.get("/api/bookmarks")
async def list_bookmarks(file_name: str = None, user = Depends(get_current_user)):
    """获取书签列表"""
    rag = get_rag()
    if file_name:
        return {"bookmarks": rag.get_bookmarks(file_name, user_id=user["user_id"])}
    return {"bookmarks": rag.get_all_bookmarks(user_id=user["user_id"])}


@app.delete("/api/bookmarks/{bookmark_id}")
async def delete_bookmark(bookmark_id: int, user = Depends(get_current_user)):
    """删除书签"""
    rag = get_rag()
    success = rag.delete_bookmark(bookmark_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}


# ===== 标签 =====

@app.post("/api/tags")
async def create_tag(request: Request, body: TagRequest, user = Depends(get_current_user)):
    """创建标签"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    tag_id = rag.create_tag(body.name, body.color)
    return {"id": tag_id, "status": "ok"}


@app.get("/api/tags")
async def list_tags(user = Depends(get_current_user)):
    """获取所有标签"""
    rag = get_rag()
    return {"tags": rag.get_tags()}


@app.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: int, user = Depends(get_current_user)):
    """删除标签"""
    rag = get_rag()
    success = rag.delete_tag(tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted"}


@app.post("/api/messages/tags")
async def tag_message(request: Request, body: MessageTagRequest, user = Depends(get_current_user)):
    """给消息打标签"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.tag_message(body.message_id, body.tag_id)
    return {"status": "ok" if success else "error"}


@app.delete("/api/messages/tags")
async def untag_message(request: Request, body: MessageTagRequest, user = Depends(get_current_user)):
    """移除消息标签"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.untag_message(body.message_id, body.tag_id)
    return {"status": "ok" if success else "error"}


# ===== SSE 流式聊天 =====

@app.post("/api/chat/stream")
async def chat_stream(request: Request, body: ChatRequest, user = Depends(get_current_user)):
    """SSE 流式聊天"""
    check_rate_limit(request.client.host)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    rag = get_rag()

    def event_generator():
        for chunk in rag.query_stream(body.question, body.session_id):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ===== 文档删除 =====

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int, user = Depends(get_current_user)):
    """删除文档"""
    rag = get_rag()
    success = rag.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id}


# ===== 会话笔记 =====

@app.get("/api/sessions/{sid}/notes")
async def get_session_notes(sid: str, user = Depends(get_current_user)):
    """获取会话笔记"""
    rag = get_rag()
    notes = rag.get_session_notes(sid)
    return {"session_id": sid, "notes": notes}


@app.patch("/api/sessions/{sid}/notes")
async def update_session_notes(sid: str, request: Request, body: NotesRequest, user = Depends(get_current_user)):
    """更新会话笔记"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    success = rag.update_session_notes(sid, body.notes)
    return {"status": "ok" if success else "error", "session_id": sid}


# ===== 收藏 =====

@app.get("/api/sessions/{sid}/favorites")
async def get_favorites(sid: str, user = Depends(get_current_user)):
    """获取收藏列表"""
    rag = get_rag()
    return {"session_id": sid, "favorites": rag.get_favorites(sid)}


@app.post("/api/sessions/{sid}/favorites")
async def add_favorite(sid: str, request: Request, body: FavoriteRequest, user = Depends(get_current_user)):
    """添加收藏"""
    check_rate_limit(request.client.host)
    rag = get_rag()
    fav_id = rag.add_favorite(sid, body.content, body.question)
    return {"id": fav_id, "status": "ok"}


@app.delete("/api/favorites/{fid}")
async def remove_favorite(fid: int, user = Depends(get_current_user)):
    """取消收藏"""
    rag = get_rag()
    success = rag.remove_favorite(fid)
    return {"status": "ok" if success else "error"}


# ===== 导出 =====

@app.get("/api/sessions/{sid}/export")
async def export_session(sid: str, format: str = Query("md", regex="^(md|html)$"), user = Depends(get_current_user)):
    """导出会话记录"""
    rag = get_rag()
    messages = rag.get_session_history(sid)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found or empty")

    from src.frontend.export import generate_export_md, generate_export_html
    if format == "html":
        content = generate_export_html(messages)
        media_type = "text/html"
        filename = f"session_{sid[:8]}.html"
    else:
        content = generate_export_md(messages)
        media_type = "text/markdown"
        filename = f"session_{sid[:8]}.md"

    return StreamingResponse(iter([content]), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })


# ===== 学习进度 =====

@app.get("/api/sessions/{sid}/progress")
async def get_learning_progress(sid: str, user = Depends(get_current_user)):
    """获取学习进度"""
    rag = get_rag()
    progress = rag.get_learning_progress(sid)
    return {"session_id": sid, **progress}


# ===== 设置 =====

@app.get("/api/settings/llm")
async def get_llm_settings(user = Depends(get_current_user)):
    """获取 LLM 配置"""
    from src.database.settings_repo import SettingsRepository
    repo = SettingsRepository()
    from src.config import get_config
    cfg = get_config()

    provider = repo.get("llm_provider") or "local"
    cloud_url = repo.get("cloud_base_url") or cfg["llm"]["fallback"]["base_url"]
    cloud_key = repo.get("cloud_api_key") or cfg["llm"]["fallback"].get("api_key", "")
    cloud_model = repo.get("cloud_model") or cfg["llm"]["fallback"]["model"]

    # API Key 脱敏
    masked_key = ""
    if cloud_key:
        if len(cloud_key) > 8:
            masked_key = cloud_key[:4] + "*" * (len(cloud_key) - 8) + cloud_key[-4:]
        else:
            masked_key = "****"

    return {
        "provider": provider,
        "local": {
            "base_url": cfg["llm"]["primary"]["base_url"],
            "model": cfg["llm"]["primary"]["model"],
        },
        "cloud": {
            "base_url": cloud_url,
            "api_key": masked_key,
            "model": cloud_model,
            "api_format": "OpenAI 兼容",
        },
    }


@app.put("/api/settings/llm")
async def update_llm_settings(body: LlmSettingsRequest, user = Depends(get_current_user)):
    """更新 LLM 配置"""
    from src.database.settings_repo import SettingsRepository
    repo = SettingsRepository()

    if body.provider not in ("local", "cloud"):
        raise HTTPException(status_code=400, detail="provider 必须为 local 或 cloud")

    repo.set("llm_provider", body.provider)

    if body.provider == "cloud":
        if body.cloud_base_url:
            repo.set("cloud_base_url", body.cloud_base_url)
        if body.cloud_api_key:
            repo.set("cloud_api_key", body.cloud_api_key)
        if body.cloud_model:
            repo.set("cloud_model", body.cloud_model)

    # 重载 LLM 客户端
    global _rag_service
    if _rag_service:
        _rag_service.reload_llm_client()

    return {"status": "ok", "provider": body.provider}


# ===== 搜索会话 =====

@app.get("/api/sessions/search")
async def search_sessions(keyword: str = Query(""), user = Depends(get_current_user)):
    """搜索会话"""
    rag = get_rag()
    if not keyword.strip():
        return {"sessions": rag.get_sessions(user_id=user["user_id"])}
    return {"sessions": rag.search_sessions(keyword, user_id=user["user_id"])}

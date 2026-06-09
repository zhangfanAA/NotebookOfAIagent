import asyncio
import os
import sys
import json
import time
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
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


# CORS 配置（使用 Bearer Token 认证，非 Cookie，允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 安全配置 =====

# JWT 认证
security = HTTPBearer(auto_error=False)

# 速率限制配置
RATE_LIMIT_WINDOW = 60  # 秒
RATE_LIMIT_MAX_REQUESTS = 30  # 每窗口最大请求数
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

# 速率限制存储
_rate_limit_store = defaultdict(list)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """从 JWT token 获取当前用户"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        from src.api.auth import verify_token
        payload = verify_token(credentials.credentials)
        return {"user_id": payload["user_id"], "username": payload["username"], "role": payload.get("role", 1)}
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


async def get_admin_user(user = Depends(get_current_user)):
    """要求管理员权限"""
    if user.get("role") != 2:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


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


def _process_usage(user_id: int, usage: dict | None, provider: str = ""):
    """处理 API 用量扣费（仅余额模型扣费）"""
    if not usage or provider != "balance":
        return
    try:
        from src.database.user_repo import UserRepository
        from src.rag.llm_client import LLMClient
        repo = UserRepository()
        cost = LLMClient.calculate_cost(
            model=usage.get("model", ""),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cache_hit_tokens=usage.get("cache_hit_tokens", 0),
        )
        if cost > 0:
            repo.update_balance(user_id, -cost)
            repo.add_usage_log(
                user_id=user_id,
                model=usage.get("model", "unknown"),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cache_hit_tokens=usage.get("cache_hit_tokens", 0),
                cache_miss_tokens=usage.get("cache_miss_tokens", 0),
                cost=cost,
            )
            logger.info("用户 %d 扣费 %.6f 元 (model=%s, tokens=%d+%d)", user_id, cost, usage.get("model"), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    except Exception as e:
        logger.error("处理用量扣费失败: %s", str(e))


# ===== 请求模型 =====

class LoginRequest(BaseModel):
    username: str
    password: str


class BanRequest(BaseModel):
    banned: bool


class RegistrationSettingRequest(BaseModel):
    allow_registration: bool


class SendMessageRequest(BaseModel):
    to_user_id: int
    content: str


class BroadcastRequest(BaseModel):
    content: str


class ChatRequest(BaseModel):
    question: str
    session_id: str


class AgentChatRequest(BaseModel):
    question: str
    session_id: str = ""


class SessionCreateRequest(BaseModel):
    title: str = "New Session"


class RenameRequest(BaseModel):
    title: str


class GenerateRequest(BaseModel):
    file_names: list
    user_prompt: str = ""
    output_type: str = "mindmap"


class BalanceAdjustRequest(BaseModel):
    amount: float


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
    provider: str  # "local" / "cloud" / "balance"
    cloud_base_url: str = ""
    cloud_api_key: str = ""
    cloud_model: str = ""
    balance_api_key: str = ""
    balance_base_url: str = ""
    balance_model: str = ""


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
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="账号已被封禁，请联系管理员")
    # 更新最后上线时间
    from src.database.user_repo import UserRepository
    UserRepository().update_last_online(user["id"])
    token = create_token(user["id"], user["username"], user["role"])
    return {"token": token, "username": user["username"], "role": user["role"]}


@app.post("/api/auth/register")
async def register(body: LoginRequest, request: Request):
    """用户注册"""
    check_rate_limit(request.client.host)

    # 注册开关检查
    from src.database.global_config_repo import GlobalConfigRepository
    if not GlobalConfigRepository().get_allow_registration():
        raise HTTPException(status_code=403, detail="当前未开放注册，请联系管理员")

    import bcrypt as _bcrypt

    username = body.username.strip()
    password = body.password

    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 个字符")

    from src.database.db_manager import DBManager
    db = DBManager()

    # 检查用户名是否已存在
    existing = db.fetch_one("SELECT id FROM users WHERE username = %s", (username,))
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 创建用户
    password_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    user_id = db.execute_returning_id(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 1)",
        (username, password_hash),
    )

    from src.api.auth import create_token
    token = create_token(user_id, username, role=1)
    return {"token": token, "username": username, "role": 1}


@app.post("/api/chat")
async def chat(request: Request, body: ChatRequest, user = Depends(get_current_user)):
    """发送消息（需要认证）"""
    check_rate_limit(request.client.host)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")

    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])

    # 余额检查（仅余额模型，管理员跳过）
    if user_llm.provider == "balance" and user.get("role") != 2:
        from src.database.user_repo import UserRepository
        u = UserRepository().get_user(user["user_id"])
        if u and float(u["balance"]) <= 0:
            raise HTTPException(status_code=402, detail="余额不足，请联系管理员充值")

    rag = get_rag()
    result = rag.query(body.question, body.session_id, llm_client=user_llm, user_id=user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # 处理用量扣费（仅余额模型）
    _process_usage(user["user_id"], result.get("usage"), provider=user_llm.provider)

    return result


@app.post("/api/upload")
async def upload_document(request: Request, file: UploadFile = File(...), user = Depends(get_current_user)):
    """上传文档（需要认证，处理在线程池中执行不阻塞事件循环）"""
    check_rate_limit(request.client.host)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制（最大 50MB）")

    # 读取客户端类型（web/app），决定使用哪个 OCR 开关
    client_type = request.headers.get("X-Client-Type", "web")
    # 桌面端本地 OCR 已完成时，跳过服务端 OCR
    local_ocr_done = request.headers.get("X-Local-OCR-Done", "false").lower() == "true"

    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    def _do_upload():
        try:
            rag = get_rag()
            return rag.upload_document(tmp_path, original_filename=file.filename, user_id=user["user_id"], client_type=client_type, skip_ocr=local_ocr_done)
        finally:
            os.unlink(tmp_path)

    try:
        result = await asyncio.to_thread(_do_upload)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        # 确保临时文件被清理
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


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
    success = rag.delete_session(sid, user_id=user["user_id"])
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
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])
    rag = get_rag()
    result = await asyncio.to_thread(
        rag.generate_content, body.file_names, body.user_prompt, body.output_type, user_llm
    )
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
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])
    rag = get_rag()
    result = await asyncio.to_thread(
        rag.generate_quiz, body.file_names, body.num_questions, body.difficulty, body.qtypes, user_llm
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/api/quiz/check")
async def check_quiz_answer(request: Request, body: QuizCheckRequest, user = Depends(get_current_user)):
    """判分"""
    check_rate_limit(request.client.host)
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])
    rag = get_rag()
    result = await asyncio.to_thread(
        rag.check_quiz_answer, body.question, body.user_answer, user_llm
    )
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
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])
    rag = get_rag()
    result = await asyncio.to_thread(
        rag.generate_flashcards, body.file_names, body.num_cards, body.topic_focus, user_llm
    )
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
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(user["user_id"])
    rag = get_rag()
    result = await asyncio.to_thread(
        rag.compare_documents, body.file_names, body.focus, user_llm
    )
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

    uid = user["user_id"]
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(uid)

    # 余额检查（仅余额模型，管理员跳过）
    if user_llm.provider == "balance" and user.get("role") != 2:
        from src.database.user_repo import UserRepository
        u = UserRepository().get_user(uid)
        if u and float(u["balance"]) <= 0:
            raise HTTPException(status_code=402, detail="余额不足，请联系管理员充值")

    rag = get_rag()
    provider = user_llm.provider

    def event_generator():
        usage_info = None
        for chunk in rag.query_stream(body.question, body.session_id, llm_client=user_llm, user_id=uid):
            if chunk.get("type") == "result" and chunk.get("data", {}).get("usage"):
                usage_info = chunk["data"]["usage"]
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        # 流结束后处理扣费（仅余额模型）
        _process_usage(uid, usage_info, provider=provider)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ===== 文档删除 =====

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int, user = Depends(get_current_user)):
    """删除文档（仅所有者或管理员可删除）"""
    rag = get_rag()
    # 权限校验：文档所有者或管理员(role=2)可删除
    doc = rag._doc_mgr._doc_repo.get_document(doc_id)
    if doc and doc.get("user_id") != user["user_id"] and user.get("role") != 2:
        raise HTTPException(status_code=403, detail="无权删除此文档")
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

    from src.utils.export import generate_export_md, generate_export_html
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
    from src.database.user_repo import UserRepository
    from src.database.global_config_repo import GlobalConfigRepository
    from src.config import get_config
    cfg = get_config()

    repo = GlobalConfigRepository()
    global_cfg = repo.get(1)  # num=1 全局云端
    balance_cfg = repo.get(2)  # num=2 余额模型
    provider = global_cfg.get("llm_provider") or "local"

    # 用户私有 key（cloud 模式下使用，优先于全局）
    user_repo = UserRepository()
    user_settings = user_repo.get_user_api_settings(user["user_id"])

    cloud_key = ""
    cloud_url = ""
    cloud_model = ""
    if user_settings:
        cloud_key = user_settings.get("cloud_api_key") or ""
        cloud_url = user_settings.get("cloud_base_url") or ""
        cloud_model = user_settings.get("cloud_model") or ""

    # 用户没有的字段回退到全局 num=1
    if not cloud_url:
        cloud_url = global_cfg.get("base_url") or cfg["llm"]["fallback"]["base_url"]
    if not cloud_key:
        cloud_key = global_cfg.get("api_key") or ""
    if not cloud_model:
        cloud_model = global_cfg.get("model") or cfg["llm"]["fallback"]["model"]

    def _mask(key: str) -> str:
        if not key:
            return ""
        if len(key) > 8:
            return key[:4] + "*" * (len(key) - 8) + key[-4:]
        return "****"

    return {
        "provider": provider,
        "is_admin": user.get("role") == 2,
        "local": {
            "base_url": cfg["llm"]["primary"]["base_url"],
            "model": cfg["llm"]["primary"]["model"],
        },
        "cloud": {
            "base_url": cloud_url,
            "api_key": _mask(cloud_key),
            "model": cloud_model,
            "api_format": "OpenAI 兼容",
        },
        "balance": {
            "base_url": balance_cfg.get("base_url") or "",
            "api_key": _mask(balance_cfg.get("api_key") or ""),
            "model": balance_cfg.get("model") or "",
        },
    }


@app.put("/api/settings/llm")
async def update_llm_settings(body: LlmSettingsRequest, user = Depends(get_current_user)):
    """更新 LLM 配置"""
    from src.database.user_repo import UserRepository
    from src.database.global_config_repo import GlobalConfigRepository

    if body.provider not in ("local", "cloud", "balance"):
        raise HTTPException(status_code=400, detail="provider 必须为 local / cloud / balance")

    global_repo = GlobalConfigRepository()
    # 更新全局 provider 设置（num=1）
    global_repo.update(1, llm_provider=body.provider)

    if body.provider == "cloud":
        # admin 可以更新全局默认（num=1）
        if user.get("role") == 2:
            global_repo.update(
                1,
                api_key=body.cloud_api_key if body.cloud_api_key else None,
                base_url=body.cloud_base_url if body.cloud_base_url else None,
                model=body.cloud_model if body.cloud_model else None,
            )
        # 所有用户都可以更新自己的 user 级配置
        UserRepository().update_user_api_settings(
            user["user_id"],
            cloud_api_key=body.cloud_api_key if body.cloud_api_key else None,
            cloud_base_url=body.cloud_base_url if body.cloud_base_url else None,
            cloud_model=body.cloud_model if body.cloud_model else None,
        )

    if body.provider == "balance" and user.get("role") == 2:
        # 余额模型配置写入 num=2
        global_repo.update(
            2,
            api_key=body.balance_api_key if body.balance_api_key else None,
            base_url=body.balance_base_url if body.balance_base_url else None,
            model=body.balance_model if body.balance_model else None,
        )

    return {"status": "ok", "provider": body.provider}


# ===== 搜索会话 =====

@app.get("/api/sessions/search")
async def search_sessions(keyword: str = Query(""), user = Depends(get_current_user)):
    """搜索会话"""
    rag = get_rag()
    if not keyword.strip():
        return {"sessions": rag.get_sessions(user_id=user["user_id"])}
    return {"sessions": rag.search_sessions(keyword, user_id=user["user_id"])}


# ===== 管理员接口 =====

@app.get("/api/admin/users")
async def admin_list_users(user = Depends(get_admin_user)):
    """获取所有用户列表"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    users = repo.list_users()
    # Decimal 序列化为 float
    for u in users:
        u["balance"] = float(u["balance"])
    return {"users": users}


@app.post("/api/admin/users/{uid}/balance")
async def admin_adjust_balance(uid: int, body: BalanceAdjustRequest, user = Depends(get_admin_user)):
    """给用户调整余额（正数加、负数减）"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    target = repo.get_user(uid)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_balance = repo.update_balance(uid, body.amount)
    return {"user_id": uid, "balance": new_balance}


@app.get("/api/admin/usage-logs")
async def admin_usage_logs(uid: int = None, page: int = 1, size: int = 20, user = Depends(get_admin_user)):
    """查看使用记录（管理员）"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    result = repo.get_usage_logs(user_id=uid, page=page, size=size)
    for item in result["items"]:
        item["cost"] = float(item["cost"])
        if isinstance(item.get("created_at"), (str,)) is False and item.get("created_at"):
            item["created_at"] = str(item["created_at"])
    return result


@app.post("/api/admin/users/{uid}/ban")
async def admin_toggle_ban(uid: int, body: BanRequest, user = Depends(get_admin_user)):
    """封号/解封用户"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    target = repo.get_user(uid)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if uid == user["user_id"]:
        raise HTTPException(status_code=400, detail="不能封禁自己")
    repo.set_banned(uid, body.banned)
    return {"user_id": uid, "banned": body.banned}


@app.get("/api/admin/settings/registration")
async def admin_get_registration(user = Depends(get_admin_user)):
    """获取注册开关状态（管理员）"""
    from src.database.global_config_repo import GlobalConfigRepository
    allowed = GlobalConfigRepository().get_allow_registration()
    return {"allow_registration": allowed}


@app.put("/api/admin/settings/registration")
async def admin_set_registration(body: RegistrationSettingRequest, user = Depends(get_admin_user)):
    """设置注册开关（管理员）"""
    from src.database.global_config_repo import GlobalConfigRepository
    GlobalConfigRepository().set_allow_registration(body.allow_registration)
    return {"allow_registration": body.allow_registration}


@app.get("/api/admin/settings/paddle-ocr")
async def admin_get_paddle_ocr(user = Depends(get_admin_user)):
    """获取 PaddleOCR 开关状态（管理员，返回网页端和桌面端两个开关）"""
    from src.database.global_config_repo import GlobalConfigRepository
    repo = GlobalConfigRepository()
    return {
        "enabled": repo.get_paddle_ocr_web_enabled(),
        "web_enabled": repo.get_paddle_ocr_web_enabled(),
        "app_enabled": repo.get_paddle_ocr_app_enabled(),
    }


class PaddleOcrSettingRequest(BaseModel):
    enabled: bool | None = None        # 向后兼容，映射到 web
    web_enabled: bool | None = None
    app_enabled: bool | None = None


@app.put("/api/admin/settings/paddle-ocr")
async def admin_set_paddle_ocr(body: PaddleOcrSettingRequest, user = Depends(get_admin_user)):
    """设置 PaddleOCR 开关（管理员，可分别设置网页端和桌面端）"""
    from src.database.global_config_repo import GlobalConfigRepository
    repo = GlobalConfigRepository()
    if body.web_enabled is not None:
        repo.set_paddle_ocr_web_enabled(body.web_enabled)
    elif body.enabled is not None:
        repo.set_paddle_ocr_web_enabled(body.enabled)
    if body.app_enabled is not None:
        repo.set_paddle_ocr_app_enabled(body.app_enabled)
    return {
        "web_enabled": repo.get_paddle_ocr_web_enabled(),
        "app_enabled": repo.get_paddle_ocr_app_enabled(),
    }


@app.get("/api/settings/paddle-ocr")
async def get_paddle_ocr_status(client_type: str = "web"):
    """获取 PaddleOCR 开关状态（公开，无需认证，根据客户端类型返回对应开关）"""
    from src.database.global_config_repo import GlobalConfigRepository
    repo = GlobalConfigRepository()
    if client_type == "app":
        enabled = repo.get_paddle_ocr_app_enabled()
    else:
        enabled = repo.get_paddle_ocr_web_enabled()
    return {"enabled": enabled}


@app.get("/api/settings/paddle-ocr/gpu")
async def get_paddle_ocr_gpu_status():
    """获取 PaddleOCR GPU 状态（公开，无需认证）"""
    from src.data.pdf_parser import get_device_info
    return get_device_info()


# ===== 公开接口 =====

@app.get("/api/settings/registration")
async def get_public_registration():
    """获取注册开关状态（公开，无需认证）"""
    from src.database.global_config_repo import GlobalConfigRepository
    allowed = GlobalConfigRepository().get_allow_registration()
    return {"allow_registration": allowed}


# ===== 用户接口 =====

@app.get("/api/user/balance")
async def get_my_balance(user = Depends(get_current_user)):
    """获取当前用户余额"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    u = repo.get_user(user["user_id"])
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"balance": float(u["balance"])}


@app.get("/api/user/usage-logs")
async def get_my_usage_logs(page: int = 1, size: int = 20, user = Depends(get_current_user)):
    """获取当前用户使用记录"""
    from src.database.user_repo import UserRepository
    repo = UserRepository()
    result = repo.get_usage_logs(user_id=user["user_id"], page=page, size=size)
    for item in result["items"]:
        item["cost"] = float(item["cost"])
        if item.get("created_at"):
            item["created_at"] = str(item["created_at"])
    return result


# ===== 站内信 =====

# 消息发送频率限制（5 秒一条）
_msg_rate_limit: dict = {}
MSG_RATE_WINDOW = 5.0


def _check_msg_rate(user_id: int):
    import time
    now = time.time()
    last = _msg_rate_limit.get(user_id, 0)
    if now - last < MSG_RATE_WINDOW:
        raise HTTPException(status_code=429, detail=f"发送太频繁，请{MSG_RATE_WINDOW}秒后再试")
    _msg_rate_limit[user_id] = now


@app.post("/api/messages")
async def send_message(body: SendMessageRequest, user = Depends(get_current_user)):
    """发送站内信"""
    _check_msg_rate(user["user_id"])
    from src.database.message_repo import MessageRepository
    from src.database.user_repo import UserRepository
    repo = MessageRepository()
    user_repo = UserRepository()

    # 普通用户只能发给管理员
    if user.get("role") != 2:
        target = user_repo.get_user(body.to_user_id)
        if not target or target.get("role") != 2:
            raise HTTPException(status_code=403, detail="只能给管理员发送消息")

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    msg_id = repo.send(user["user_id"], body.to_user_id, body.content.strip())
    return {"id": msg_id, "status": "sent"}


@app.post("/api/messages/broadcast")
async def broadcast_message(body: BroadcastRequest, user = Depends(get_current_user)):
    """群发消息（仅管理员）"""
    if user.get("role") != 2:
        raise HTTPException(status_code=403, detail="仅管理员可群发消息")
    _check_msg_rate(user["user_id"])
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    from src.database.message_repo import MessageRepository
    count = MessageRepository().broadcast(user["user_id"], body.content.strip())
    return {"status": "sent", "count": count}


@app.get("/api/messages/inbox")
async def get_inbox(page: int = 1, size: int = 20, user = Depends(get_current_user)):
    """收件箱"""
    from src.database.message_repo import MessageRepository
    result = MessageRepository().get_inbox(user["user_id"], page, size)
    for item in result["items"]:
        if item.get("created_at"):
            item["created_at"] = str(item["created_at"])
    return result


@app.get("/api/messages/sent")
async def get_sent(page: int = 1, size: int = 20, user = Depends(get_current_user)):
    """已发送"""
    from src.database.message_repo import MessageRepository
    result = MessageRepository().get_sent(user["user_id"], page, size)
    for item in result["items"]:
        if item.get("created_at"):
            item["created_at"] = str(item["created_at"])
    return result


@app.get("/api/messages/unread-count")
async def get_unread_count(user = Depends(get_current_user)):
    """未读消息数"""
    from src.database.message_repo import MessageRepository
    count = MessageRepository().get_unread_count(user["user_id"])
    return {"count": count}


@app.put("/api/messages/{msg_id}/read")
async def mark_read(msg_id: int, user = Depends(get_current_user)):
    """标记已读"""
    from src.database.message_repo import MessageRepository
    ok = MessageRepository().mark_read(msg_id, user["user_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="消息不存在")
    return {"status": "ok"}


@app.put("/api/messages/read-all")
async def mark_all_read(user = Depends(get_current_user)):
    """全部标记已读"""
    from src.database.message_repo import MessageRepository
    count = MessageRepository().mark_all_read(user["user_id"])
    return {"marked": count}


# ===== 下载文件管理 =====

DOWNLOAD_DIR = os.path.join(get_config()["data_dir"], "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.get("/api/downloads")
async def list_download_files(user = Depends(get_current_user)):
    """列出所有可下载文件"""
    from src.database.download_repo import DownloadFileRepository
    files = DownloadFileRepository().list_all()
    for f in files:
        if f.get("uploaded_at"):
            f["uploaded_at"] = str(f["uploaded_at"])
    return {"files": files}


@app.post("/api/downloads")
async def upload_download_file(request: Request, file: UploadFile = File(...), user = Depends(get_admin_user)):
    """管理员上传文件到下载区"""
    check_rate_limit(request.client.host)
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制（最大 100MB）")

    # 保存文件
    safe_name = file.filename or "unnamed"
    file_path = os.path.join(DOWNLOAD_DIR, safe_name)
    # 同名文件处理
    if os.path.exists(file_path):
        name, ext = os.path.splitext(safe_name)
        import time as _time
        safe_name = f"{name}_{int(_time.time())}{ext}"
        file_path = os.path.join(DOWNLOAD_DIR, safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    from src.database.download_repo import DownloadFileRepository
    file_id = DownloadFileRepository().create(
        file_name=safe_name,
        file_path=file_path,
        file_size=len(content),
        uploaded_by=user["user_id"],
    )
    return {"status": "ok", "id": file_id}


@app.delete("/api/downloads/{file_id}")
async def delete_download_file(file_id: int, user = Depends(get_admin_user)):
    """管理员删除下载文件"""
    from src.database.download_repo import DownloadFileRepository
    repo = DownloadFileRepository()
    record = repo.get_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 删除物理文件
    if record.get("file_path") and os.path.exists(record["file_path"]):
        os.unlink(record["file_path"])

    repo.delete(file_id)
    return {"status": "ok"}


@app.get("/api/downloads/{file_id}/file")
async def download_file(file_id: int, user = Depends(get_current_user)):
    """下载文件"""
    from src.database.download_repo import DownloadFileRepository
    record = DownloadFileRepository().get_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not record.get("file_path") or not os.path.exists(record["file_path"]):
        raise HTTPException(status_code=404, detail="文件已被删除")
    return FileResponse(
        path=record["file_path"],
        filename=record["file_name"],
        media_type="application/octet-stream",
    )


# ===== Supervisor Agent =====

@app.post("/api/agent/chat")
async def agent_chat(request: Request, body: AgentChatRequest, user = Depends(get_current_user)):
    """Supervisor Agent 非流式对话"""
    check_rate_limit(request.client.host)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")

    uid = user["user_id"]

    # 余额检查
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(uid)
    if user_llm.provider == "balance" and user.get("role") != 2:
        from src.database.user_repo import UserRepository
        u = UserRepository().get_user(uid)
        if u and float(u["balance"]) <= 0:
            raise HTTPException(status_code=402, detail="余额不足，请联系管理员充值")

    from src.supervisor.graph import SupervisorGraph

    async with SupervisorGraph(user_id=uid, session_id=body.session_id or None) as supervisor:
        result = await supervisor.ainvoke(body.question)

    return result


@app.post("/api/agent/stream")
async def agent_stream(request: Request, body: AgentChatRequest, user = Depends(get_current_user)):
    """Supervisor Agent SSE 流式对话"""
    check_rate_limit(request.client.host)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")

    uid = user["user_id"]

    # 余额检查
    from src.rag.llm_client import LLMClient
    user_llm = LLMClient.for_user(uid)
    provider = user_llm.provider
    if provider == "balance" and user.get("role") != 2:
        from src.database.user_repo import UserRepository
        u = UserRepository().get_user(uid)
        if u and float(u["balance"]) <= 0:
            raise HTTPException(status_code=402, detail="余额不足，请联系管理员充值")

    async def event_generator():
        from src.supervisor.graph import SupervisorGraph

        async with SupervisorGraph(user_id=uid, session_id=body.session_id or None) as supervisor:
            async for event in supervisor.astream(body.question):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })

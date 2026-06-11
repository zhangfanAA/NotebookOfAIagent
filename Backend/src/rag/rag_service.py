"""
RAGService — 统一 RAG 服务接口（门面模式）
负责: RAG

精简门面，功能已拆分至:
- session_manager.py  — 会话 CRUD、笔记、收藏
- query_engine.py     — 查询核心逻辑（检索+生成）
- document_manager.py — 文档上传/删除管理
"""

from src.rag.session_manager import SessionManager
from src.rag.query_engine import QueryEngine
from src.rag.document_manager import DocumentManager
from src.rag.mindmap_generator import MindmapGenerator
from src.rag.quiz_generator import QuizGenerator
from src.rag.flashcard_generator import FlashcardGenerator
from src.rag.compare_generator import CompareGenerator
from src.database.reading_repo import ReadingRepository
from src.database.bookmark_repo import BookmarkRepository
from src.database.tag_repo import TagRepository
from src.logger import get_logger
import time

logger = get_logger("rag.rag_service")


class _TTLCache:
    """简单的 TTL 内存缓存"""

    def __init__(self):
        self._store = {}

    def get(self, key: str, ttl: float = 5.0):
        """获取缓存，过期返回 None"""
        item = self._store.get(key)
        if item and time.time() - item[1] < ttl:
            return item[0]
        return None

    def set(self, key: str, value):
        """写入缓存"""
        self._store[key] = (value, time.time())

    def invalidate(self, prefix: str = ""):
        """清除匹配前缀的缓存"""
        if not prefix:
            self._store.clear()
        else:
            self._store = {k: v for k, v in self._store.items() if not k.startswith(prefix)}


class RAGService:
    """
    RAG 服务核心接口（门面模式）

    供 FULL 的 Streamlit/FastAPI 调用，所有方法返回标准 dict。
    禁止抛出未捕获异常。
    """

    def __init__(self):
        self._session_mgr = SessionManager()
        self._query_engine = QueryEngine(self._session_mgr)
        self._doc_mgr = DocumentManager()
        self._mindmap_gen = MindmapGenerator()
        self._quiz_gen = QuizGenerator()
        self._flashcard_gen = FlashcardGenerator()
        self._compare_gen = CompareGenerator()
        self._reading_repo = ReadingRepository()
        self._bookmark_repo = BookmarkRepository()
        self._tag_repo = TagRepository()
        self._cache = _TTLCache()
        logger.info("RAGService 初始化完成")

    # ===== 查询相关 =====

    def query(self, question: str, session_id: str, llm_client=None, user_id=None, memory_mode=False) -> dict:
        """核心查询接口"""
        return self._query_engine.query(question, session_id, llm_client=llm_client, user_id=user_id, memory_mode=memory_mode)

    def query_stream(self, question: str, session_id: str, llm_client=None, user_id=None, memory_mode=False):
        """流式查询接口"""
        yield from self._query_engine.query_stream(question, session_id, llm_client=llm_client, user_id=user_id, memory_mode=memory_mode)

    def reload_llm_client(self):
        """重新加载 LLM 客户端（设置变更后调用）"""
        from src.rag.llm_client import LLMClient
        self._query_engine._llm_client = LLMClient()
        logger.info("LLM 客户端已重新加载: provider=%s", self._query_engine._llm_client.provider)

    @staticmethod
    def _with_llm(generator, llm_client, fn):
        """临时替换生成器的 LLM 客户端，调用完成后恢复"""
        if not llm_client:
            return fn()
        original = generator._llm
        generator._llm = llm_client
        try:
            return fn()
        finally:
            generator._llm = original

    # ===== 会话相关 =====

    def create_session(self, title: str = "新会话", user_id: int = None) -> str:
        """创建新会话"""
        return self._session_mgr.create_session(title, user_id)

    def get_sessions(self, user_id: int = None) -> list:
        """获取会话列表（带缓存）"""
        cache_key = f"sessions_{user_id}"
        cached = self._cache.get(cache_key, ttl=3.0)
        if cached is not None:
            return cached
        result = self._session_mgr.get_sessions(user_id)
        self._cache.set(cache_key, result)
        return result

    def search_sessions(self, keyword: str, user_id: int = None) -> list:
        """搜索会话"""
        return self._session_mgr.search_sessions(keyword, user_id)

    def delete_session(self, session_id: str, user_id: int = None) -> bool:
        """删除会话（同时清理聊天记录向量）"""
        from src.rag import chat_history_store
        try:
            # 如果未传入 user_id，从会话记录中查询
            if user_id is None:
                session_info = self._session_mgr._session_repo.get_session(session_id)
                if session_info:
                    user_id = session_info.get("user_id")
            chat_history_store.delete_by_session(session_id, user_id=user_id)
        except Exception as e:
            logger.warning("清理聊天向量失败: %s", str(e))
        result = self._session_mgr.delete_session(session_id)
        self._cache.invalidate("sessions")
        return result

    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        return self._session_mgr.update_session_title(session_id, title)

    def get_session_history(self, session_id: str) -> list:
        """获取会话历史"""
        return self._session_mgr.get_session_history(session_id)

    def update_session_notes(self, session_id: str, notes: str) -> bool:
        """更新会话笔记"""
        return self._session_mgr.update_session_notes(session_id, notes)

    def get_session_notes(self, session_id: str) -> str:
        """获取会话笔记"""
        return self._session_mgr.get_session_notes(session_id)

    def add_favorite(self, session_id: str, content: str, question: str = None) -> int:
        """添加收藏"""
        return self._session_mgr.add_favorite(session_id, content, question)

    def remove_favorite(self, favorite_id: int) -> bool:
        """取消收藏"""
        return self._session_mgr.remove_favorite(favorite_id)

    def get_favorites(self, session_id: str) -> list:
        """获取收藏列表"""
        return self._session_mgr.get_favorites(session_id)

    # ===== 文档相关 =====

    def upload_document(self, file_path: str, original_filename: str = None, user_id: int = None) -> dict:
        """上传文档"""
        result = self._doc_mgr.upload_document(file_path, original_filename, user_id)
        self._cache.invalidate("documents")
        self._cache.invalidate("vdb_stats")
        return result

    def get_documents(self, user_id: int = None) -> list:
        """获取文档列表（带缓存）"""
        cache_key = f"documents_{user_id}"
        cached = self._cache.get(cache_key, ttl=5.0)
        if cached is not None:
            return cached
        result = self._doc_mgr.get_documents(user_id)
        self._cache.set(cache_key, result)
        return result

    def delete_document(self, doc_id: int) -> bool:
        """删除文档"""
        result = self._doc_mgr.delete_document(doc_id)
        self._cache.invalidate("documents")
        self._cache.invalidate("vdb_stats")
        return result

    def get_vector_db_stats(self) -> dict:
        """获取向量库统计（带缓存）"""
        cached = self._cache.get("vdb_stats", ttl=10.0)
        if cached is not None:
            return cached
        result = self._doc_mgr.get_vector_db_stats()
        self._cache.set("vdb_stats", result)
        return result

    # ===== 思维导图/笔记生成 =====

    def generate_content(self, file_names: list, user_prompt: str = "", output_type: str = "mindmap", llm_client=None) -> dict:
        """生成思维导图或重点笔记"""
        return self._with_llm(self._mindmap_gen, llm_client, lambda: self._mindmap_gen.generate(file_names, user_prompt, output_type))

    # ===== 测验相关 =====

    def generate_quiz(self, file_names: list, num_questions: int = 5, difficulty: str = "medium", qtypes: list = None, llm_client=None) -> dict:
        """生成测验题目"""
        return self._with_llm(self._quiz_gen, llm_client, lambda: self._quiz_gen.generate(file_names, num_questions, difficulty, qtypes))

    def check_quiz_answer(self, question: dict, user_answer: str, llm_client=None) -> dict:
        """判分"""
        return self._with_llm(self._quiz_gen, llm_client, lambda: self._quiz_gen.check_answer(question, user_answer))

    # ===== 闪卡相关 =====

    def generate_flashcards(self, file_names: list, num_cards: int = 10, topic_focus: str = "", llm_client=None) -> dict:
        """生成闪卡"""
        return self._with_llm(self._flashcard_gen, llm_client, lambda: self._flashcard_gen.generate(file_names, num_cards, topic_focus))

    # ===== 文档对比 =====

    def compare_documents(self, file_names: list, focus: str = "", llm_client=None) -> dict:
        """对比文档"""
        return self._with_llm(self._compare_gen, llm_client, lambda: self._compare_gen.generate(file_names, focus))

    # ===== 阅读进度 =====

    def update_reading_progress(self, file_name: str, current_page: int, total_pages: int = 0, user_id: int = None) -> bool:
        return self._reading_repo.update_progress(file_name, current_page, total_pages, user_id)

    def get_reading_progress(self, file_name: str, user_id: int = None) -> dict:
        return self._reading_repo.get_progress(file_name, user_id)

    def get_all_reading_progress(self, user_id: int = None) -> list:
        cache_key = f"reading_progress_{user_id}"
        cached = self._cache.get(cache_key, ttl=5.0)
        if cached is not None:
            return cached
        result = self._reading_repo.get_all_progress(user_id)
        self._cache.set(cache_key, result)
        return result

    # ===== 书签 =====

    def add_bookmark(self, file_name: str, page_number: int, title: str = None, note: str = None, user_id: int = None) -> int:
        return self._bookmark_repo.add_bookmark(file_name, page_number, title, note, user_id)

    def get_bookmarks(self, file_name: str, user_id: int = None) -> list:
        return self._bookmark_repo.get_bookmarks(file_name, user_id)

    def get_all_bookmarks(self, user_id: int = None) -> list:
        cache_key = f"bookmarks_{user_id}"
        cached = self._cache.get(cache_key, ttl=5.0)
        if cached is not None:
            return cached
        result = self._bookmark_repo.get_all_bookmarks(user_id)
        self._cache.set(cache_key, result)
        return result

    def delete_bookmark(self, bookmark_id: int) -> bool:
        return self._bookmark_repo.delete_bookmark(bookmark_id)

    # ===== 标签 =====

    def create_tag(self, name: str, color: str = "#5ac8fa") -> int:
        return self._tag_repo.create_tag(name, color)

    def get_tags(self) -> list:
        return self._tag_repo.get_tags()

    def delete_tag(self, tag_id: int) -> bool:
        return self._tag_repo.delete_tag(tag_id)

    def tag_message(self, message_id: int, tag_id: int) -> bool:
        return self._tag_repo.tag_message(message_id, tag_id)

    def untag_message(self, message_id: int, tag_id: int) -> bool:
        return self._tag_repo.untag_message(message_id, tag_id)

    def get_message_tags(self, message_id: int) -> list:
        return self._tag_repo.get_message_tags(message_id)

    # ===== 诊断相关 =====

    def get_weak_topics(self, session_id: str) -> list:
        """获取薄弱知识点"""
        return self._query_engine.get_weak_topics(session_id)

    def get_conversation_summary(self, session_id: str) -> dict:
        """获取对话摘要"""
        return self._query_engine.get_conversation_summary(session_id)

    def get_recent_topics(self, session_id: str) -> list:
        """获取最近话题"""
        return self._query_engine.get_recent_topics(session_id)

    def get_learning_progress(self, session_id: str) -> dict:
        """获取学习进度"""
        return self._query_engine.get_learning_progress(session_id)

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
from src.logger import get_logger

logger = get_logger("rag.rag_service")


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
        logger.info("RAGService 初始化完成")

    # ===== 查询相关 =====

    def query(self, question: str, session_id: str) -> dict:
        """核心查询接口"""
        return self._query_engine.query(question, session_id)

    def query_stream(self, question: str, session_id: str):
        """流式查询接口"""
        yield from self._query_engine.query_stream(question, session_id)

    # ===== 会话相关 =====

    def create_session(self, title: str = "新会话") -> str:
        """创建新会话"""
        return self._session_mgr.create_session(title)

    def get_sessions(self) -> list:
        """获取会话列表"""
        return self._session_mgr.get_sessions()

    def search_sessions(self, keyword: str) -> list:
        """搜索会话"""
        return self._session_mgr.search_sessions(keyword)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return self._session_mgr.delete_session(session_id)

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

    def upload_document(self, file_path: str) -> dict:
        """上传文档"""
        return self._doc_mgr.upload_document(file_path)

    def get_documents(self) -> list:
        """获取文档列表"""
        return self._doc_mgr.get_documents()

    def delete_document(self, doc_id: int) -> bool:
        """删除文档"""
        return self._doc_mgr.delete_document(doc_id)

    def get_vector_db_stats(self) -> dict:
        """获取向量库统计"""
        return self._doc_mgr.get_vector_db_stats()

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

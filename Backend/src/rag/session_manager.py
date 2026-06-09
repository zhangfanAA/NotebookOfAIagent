"""
RAG 会话管理模块
负责: RAG

封装会话 CRUD、笔记、收藏等操作。
"""

from src.database.session_repo import SessionRepository, MessageRepository
from src.logger import get_logger

logger = get_logger("rag.session_manager")


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self._session_repo = SessionRepository()
        self._message_repo = MessageRepository()

    def create_session(self, title: str = "新会话", user_id: int = None) -> str:
        """创建新会话，返回 session_id"""
        return self._session_repo.create_session(title, user_id)

    def get_sessions(self, user_id: int = None) -> list:
        """获取会话列表"""
        return self._session_repo.get_sessions(user_id=user_id)

    def search_sessions(self, keyword: str, user_id: int = None) -> list:
        """搜索会话（标题 + 内容）"""
        return self._session_repo.search_sessions(keyword, user_id=user_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return self._session_repo.delete_session(session_id)

    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        return self._session_repo.update_title(session_id, title)

    def get_session_history(self, session_id: str) -> list:
        """获取会话历史记录"""
        messages = self._message_repo.get_messages(session_id)
        return [
            {
                "role": m["role"],
                "content": m["content"],
                "timestamp": m.get("created_at", ""),
                "sources": m.get("sources"),
                "confidence": m.get("confidence"),
            }
            for m in messages
        ]

    def update_session_notes(self, session_id: str, notes: str) -> bool:
        """更新会话笔记"""
        return self._session_repo.update_notes(session_id, notes)

    def get_session_notes(self, session_id: str) -> str:
        """获取会话笔记"""
        return self._session_repo.get_notes(session_id)

    def add_favorite(self, session_id: str, content: str, question: str = None) -> int:
        """添加收藏"""
        return self._session_repo.add_favorite(session_id, content, question)

    def remove_favorite(self, favorite_id: int) -> bool:
        """取消收藏"""
        return self._session_repo.remove_favorite(favorite_id)

    def get_favorites(self, session_id: str) -> list:
        """获取收藏列表"""
        return self._session_repo.get_favorites(session_id)

    def get_recent_context(self, session_id: str, turns: int = 3) -> list:
        """获取最近上下文"""
        return self._message_repo.get_recent_context(session_id, turns)

    def add_message(self, session_id: str, role: str, content: str, **kwargs) -> int:
        """添加消息"""
        return self._message_repo.add_message(session_id, role, content, **kwargs)

    def get_messages(self, session_id: str) -> list:
        """获取所有消息"""
        return self._message_repo.get_messages(session_id)

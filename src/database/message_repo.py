"""
站内信仓库
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.message_repo")


class MessageRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def send(self, from_user_id: int, to_user_id: int, content: str) -> int:
        """发送消息，返回消息 ID"""
        msg_id = self.db.execute_returning_id(
            "INSERT INTO user_messages (from_user_id, to_user_id, content) VALUES (%s, %s, %s)",
            (from_user_id, to_user_id, content),
        )
        logger.info("站内信: %d → %d (id=%d)", from_user_id, to_user_id, msg_id)
        return msg_id

    def get_inbox(self, user_id: int, page: int = 1, size: int = 20) -> dict:
        """收件箱（收到的消息）"""
        offset = (page - 1) * size
        items = self.db.fetch_all(
            "SELECT m.*, u.username AS from_username "
            "FROM user_messages m LEFT JOIN users u ON m.from_user_id = u.id "
            "WHERE m.to_user_id = %s ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
            (user_id, size, offset),
        )
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM user_messages WHERE to_user_id = %s", (user_id,)
        )
        return {"items": items, "total": row["total"] if row else 0, "page": page, "size": size}

    def get_sent(self, user_id: int, page: int = 1, size: int = 20) -> dict:
        """已发送"""
        offset = (page - 1) * size
        items = self.db.fetch_all(
            "SELECT m.*, u.username AS to_username "
            "FROM user_messages m LEFT JOIN users u ON m.to_user_id = u.id "
            "WHERE m.from_user_id = %s ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
            (user_id, size, offset),
        )
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM user_messages WHERE from_user_id = %s", (user_id,)
        )
        return {"items": items, "total": row["total"] if row else 0, "page": page, "size": size}

    def get_unread_count(self, user_id: int) -> int:
        """未读消息数"""
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM user_messages WHERE to_user_id = %s AND is_read = 0",
            (user_id,),
        )
        return row["cnt"] if row else 0

    def mark_read(self, message_id: int, user_id: int) -> bool:
        """标记单条已读（只能标记发给自己的）"""
        affected = self.db.execute(
            "UPDATE user_messages SET is_read = 1 WHERE id = %s AND to_user_id = %s",
            (message_id, user_id),
        )
        return affected > 0

    def mark_all_read(self, user_id: int) -> int:
        """全部标记已读"""
        affected = self.db.execute(
            "UPDATE user_messages SET is_read = 1 WHERE to_user_id = %s AND is_read = 0",
            (user_id,),
        )
        return affected

    def broadcast(self, from_user_id: int, content: str, exclude_user_ids: list = None) -> int:
        """群发消息给所有用户，返回发送条数"""
        # 获取所有普通用户
        users = self.db.fetch_all("SELECT id FROM users WHERE role = 1")
        if exclude_user_ids:
            users = [u for u in users if u["id"] not in exclude_user_ids]
        count = 0
        for u in users:
            self.db.execute(
                "INSERT INTO user_messages (from_user_id, to_user_id, content) VALUES (%s, %s, %s)",
                (from_user_id, u["id"], content),
            )
            count += 1
        logger.info("群发消息: from=%d count=%d", from_user_id, count)
        return count

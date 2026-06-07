"""
标签数据仓库
负责: FULL
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.tag_repo")


class TagRepository:
    """标签 CRUD"""

    def __init__(self):
        self._db = DBManager()

    def create_tag(self, name: str, color: str = "#5ac8fa") -> int:
        """创建标签"""
        sql = "INSERT IGNORE INTO tags (name, color) VALUES (%s, %s)"
        self._db.execute(sql, (name, color))
        row = self._db.fetch_one("SELECT id FROM tags WHERE name=%s", (name,))
        return row["id"] if row else 0

    def get_tags(self) -> list:
        """获取所有标签"""
        return self._db.fetch_all("SELECT * FROM tags ORDER BY name")

    def delete_tag(self, tag_id: int) -> bool:
        """删除标签"""
        return self._db.execute("DELETE FROM tags WHERE id=%s", (tag_id,)) > 0

    def tag_message(self, message_id: int, tag_id: int) -> bool:
        """给消息打标签"""
        sql = "INSERT IGNORE INTO message_tags (message_id, tag_id) VALUES (%s, %s)"
        return self._db.execute(sql, (message_id, tag_id)) > 0

    def untag_message(self, message_id: int, tag_id: int) -> bool:
        """移除消息标签"""
        return self._db.execute("DELETE FROM message_tags WHERE message_id=%s AND tag_id=%s", (message_id, tag_id)) > 0

    def get_message_tags(self, message_id: int) -> list:
        """获取消息的所有标签"""
        return self._db.fetch_all(
            "SELECT t.* FROM tags t JOIN message_tags mt ON t.id=mt.tag_id WHERE mt.message_id=%s",
            (message_id,),
        )

    def get_messages_by_tag(self, tag_id: int) -> list:
        """获取标签下的所有消息 ID"""
        return self._db.fetch_all("SELECT message_id FROM message_tags WHERE tag_id=%s", (tag_id,))

"""
书签数据仓库
负责: FULL
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.bookmark_repo")


class BookmarkRepository:
    """书签 CRUD"""

    def __init__(self):
        self._db = DBManager()

    def add_bookmark(self, file_name: str, page_number: int, title: str = None, note: str = None, user_id: int = None) -> int:
        """添加书签"""
        sql = "INSERT INTO bookmarks (file_name, page_number, title, note, user_id) VALUES (%s, %s, %s, %s, %s)"
        return self._db.execute_returning_id(sql, (file_name, page_number, title, note, user_id))

    def get_bookmarks(self, file_name: str, user_id: int = None) -> list:
        """获取文件的所有书签"""
        if user_id:
            return self._db.fetch_all(
                "SELECT * FROM bookmarks WHERE file_name=%s AND user_id=%s ORDER BY page_number",
                (file_name, user_id),
            )
        return self._db.fetch_all(
            "SELECT * FROM bookmarks WHERE file_name=%s ORDER BY page_number",
            (file_name,),
        )

    def get_all_bookmarks(self, user_id: int = None) -> list:
        """获取所有书签"""
        if user_id:
            return self._db.fetch_all("SELECT * FROM bookmarks WHERE user_id=%s ORDER BY file_name, page_number", (user_id,))
        return self._db.fetch_all("SELECT * FROM bookmarks ORDER BY file_name, page_number")

    def update_bookmark(self, bookmark_id: int, title: str = None, note: str = None) -> bool:
        """更新书签"""
        parts = []
        params = []
        if title is not None:
            parts.append("title=%s")
            params.append(title)
        if note is not None:
            parts.append("note=%s")
            params.append(note)
        if not parts:
            return False
        params.append(bookmark_id)
        sql = f"UPDATE bookmarks SET {', '.join(parts)} WHERE id=%s"
        return self._db.execute(sql, tuple(params)) > 0

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """删除书签"""
        return self._db.execute("DELETE FROM bookmarks WHERE id=%s", (bookmark_id,)) > 0

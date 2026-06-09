"""
阅读进度数据仓库
负责: FULL
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.reading_repo")


class ReadingRepository:
    """阅读进度 CRUD"""

    def __init__(self):
        self._db = DBManager()

    def update_progress(self, file_name: str, current_page: int, total_pages: int = 0, user_id: int = None) -> bool:
        """更新阅读进度"""
        is_finished = 1 if total_pages > 0 and current_page >= total_pages else 0
        sql = """
            INSERT INTO reading_progress (file_name, current_page, total_pages, is_finished, user_id)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE current_page=%s, total_pages=%s, is_finished=%s
        """
        affected = self._db.execute(sql, (file_name, current_page, total_pages, is_finished, user_id, current_page, total_pages, is_finished))
        return affected > 0

    def get_progress(self, file_name: str, user_id: int = None) -> dict:
        """获取单个文件的阅读进度"""
        if user_id:
            return self._db.fetch_one("SELECT * FROM reading_progress WHERE file_name=%s AND user_id=%s", (file_name, user_id))
        return self._db.fetch_one("SELECT * FROM reading_progress WHERE file_name=%s", (file_name,))

    def get_all_progress(self, user_id: int = None) -> list:
        """获取所有文件的阅读进度"""
        if user_id:
            return self._db.fetch_all("SELECT * FROM reading_progress WHERE user_id=%s ORDER BY updated_at DESC", (user_id,))
        return self._db.fetch_all("SELECT * FROM reading_progress ORDER BY updated_at DESC")

    def delete_progress(self, file_name: str) -> bool:
        """删除阅读进度"""
        affected = self._db.execute("DELETE FROM reading_progress WHERE file_name=%s", (file_name,))
        return affected > 0

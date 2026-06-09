"""下载文件仓库"""

from src.database.db_manager import DBManager


class DownloadFileRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def create(self, file_name: str, file_path: str, file_size: int, uploaded_by: int = None) -> int:
        return self.db.execute_returning_id(
            "INSERT INTO download_files (file_name, file_path, file_size, uploaded_by) VALUES (%s, %s, %s, %s)",
            (file_name, file_path, file_size, uploaded_by),
        )

    def list_all(self) -> list[dict]:
        return self.db.fetch_all(
            "SELECT id, file_name, file_size, uploaded_by, uploaded_at FROM download_files ORDER BY uploaded_at DESC"
        )

    def get_by_id(self, file_id: int) -> dict:
        return self.db.fetch_one("SELECT * FROM download_files WHERE id = %s", (file_id,))

    def delete(self, file_id: int):
        self.db.execute("DELETE FROM download_files WHERE id = %s", (file_id,))

"""
设置存储仓库
"""

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.settings_repo")


class SettingsRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def get(self, key: str) -> str | None:
        sql = "SELECT value FROM settings WHERE `key` = %s"
        row = self.db.fetch_one(sql, (key,))
        return row["value"] if row else None

    def set(self, key: str, value: str):
        sql = """
            INSERT INTO settings (`key`, `value`) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value` = VALUES(value)
        """
        self.db.execute(sql, (key, value))

    def get_all(self) -> dict:
        sql = "SELECT `key`, `value` FROM settings"
        rows = self.db.fetch_all(sql)
        return {r["key"]: r["value"] for r in rows}

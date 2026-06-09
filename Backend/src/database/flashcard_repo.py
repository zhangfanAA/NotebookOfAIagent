"""
闪卡存储仓库
"""

import json
from datetime import datetime

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.flashcard_repo")


class FlashcardRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def save(self, title: str, cards: list, file_names: list = None, user_id: int = None) -> int:
        sql = """
            INSERT INTO saved_flashcards (title, cards, file_names, user_id)
            VALUES (%s, %s, %s, %s)
        """
        c_json = json.dumps(cards, ensure_ascii=False)
        fn_json = json.dumps(file_names, ensure_ascii=False) if file_names else None
        fc_id = self.db.execute_returning_id(sql, (title, c_json, fn_json, user_id))
        logger.info("保存闪卡集: id=%d title=%s cards=%d user_id=%s", fc_id, title, len(cards), user_id)
        return fc_id

    def list(self, limit: int = 50, user_id: int = None) -> list:
        if user_id:
            sql = "SELECT id, title, file_names, created_at FROM saved_flashcards WHERE user_id = %s ORDER BY created_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (user_id, limit))
        else:
            sql = "SELECT id, title, file_names, created_at FROM saved_flashcards ORDER BY created_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (limit,))
        for r in results:
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
            if isinstance(r.get("file_names"), str):
                r["file_names"] = json.loads(r["file_names"])
        return results

    def get(self, flashcard_id: int) -> dict:
        sql = "SELECT * FROM saved_flashcards WHERE id = %s"
        result = self.db.fetch_one(sql, (flashcard_id,))
        if result:
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("file_names"), str):
                result["file_names"] = json.loads(result["file_names"])
            if isinstance(result.get("cards"), str):
                result["cards"] = json.loads(result["cards"])
        return result

    def delete(self, flashcard_id: int) -> bool:
        sql = "DELETE FROM saved_flashcards WHERE id = %s"
        affected = self.db.execute(sql, (flashcard_id,))
        logger.info("删除闪卡集: id=%d", flashcard_id)
        return affected > 0

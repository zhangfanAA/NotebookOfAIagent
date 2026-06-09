"""
测验存储仓库
"""

import json
from datetime import datetime

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.quiz_repo")


class QuizRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def save(self, title: str, questions: list, score_correct: int = 0, score_total: int = 0, difficulty: str = "medium", file_names: list = None, user_id: int = None) -> int:
        sql = """
            INSERT INTO saved_quizzes (title, questions, score_correct, score_total, difficulty, file_names, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        q_json = json.dumps(questions, ensure_ascii=False)
        fn_json = json.dumps(file_names, ensure_ascii=False) if file_names else None
        quiz_id = self.db.execute_returning_id(sql, (title, q_json, score_correct, score_total, difficulty, fn_json, user_id))
        logger.info("保存测验: id=%d title=%s score=%d/%d user_id=%s", quiz_id, title, score_correct, score_total, user_id)
        return quiz_id

    def list(self, limit: int = 50, user_id: int = None) -> list:
        if user_id:
            sql = "SELECT id, title, score_correct, score_total, difficulty, file_names, created_at FROM saved_quizzes WHERE user_id = %s ORDER BY created_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (user_id, limit))
        else:
            sql = "SELECT id, title, score_correct, score_total, difficulty, file_names, created_at FROM saved_quizzes ORDER BY created_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (limit,))
        for r in results:
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
            if isinstance(r.get("file_names"), str):
                r["file_names"] = json.loads(r["file_names"])
        return results

    def get(self, quiz_id: int) -> dict:
        sql = "SELECT * FROM saved_quizzes WHERE id = %s"
        result = self.db.fetch_one(sql, (quiz_id,))
        if result:
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("file_names"), str):
                result["file_names"] = json.loads(result["file_names"])
            if isinstance(result.get("questions"), str):
                result["questions"] = json.loads(result["questions"])
        return result

    def delete(self, quiz_id: int) -> bool:
        sql = "DELETE FROM saved_quizzes WHERE id = %s"
        affected = self.db.execute(sql, (quiz_id,))
        logger.info("删除测验: id=%d", quiz_id)
        return affected > 0

"""
思维导图/笔记存储仓库
"""

import json
from datetime import datetime

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.mindmap_repo")


class MindmapRepository:
    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def save(self, title: str, output_type: str, content: str, mermaid_code: str = None, file_names: list = None, user_id: int = None) -> int:
        sql = """
            INSERT INTO saved_mindmaps (title, output_type, content, mermaid_code, file_names, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        fn_json = json.dumps(file_names, ensure_ascii=False) if file_names else None
        mindmap_id = self.db.execute_returning_id(sql, (title, output_type, content, mermaid_code, fn_json, user_id))
        logger.info("保存思维导图: id=%d title=%s type=%s user_id=%s", mindmap_id, title, output_type, user_id)
        return mindmap_id

    def list(self, output_type: str = None, limit: int = 50, user_id: int = None) -> list:
        conditions = []
        params = []
        if output_type:
            conditions.append("output_type = %s")
            params.append(output_type)
        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT id, title, output_type, file_names, created_at FROM saved_mindmaps {where} ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        results = self.db.fetch_all(sql, tuple(params))
        for r in results:
            if isinstance(r.get("created_at"), datetime):
                r["created_at"] = r["created_at"].isoformat()
            if isinstance(r.get("file_names"), str):
                r["file_names"] = json.loads(r["file_names"])
        return results

    def get(self, mindmap_id: int) -> dict:
        sql = "SELECT * FROM saved_mindmaps WHERE id = %s"
        result = self.db.fetch_one(sql, (mindmap_id,))
        if result:
            if isinstance(result.get("created_at"), datetime):
                result["created_at"] = result["created_at"].isoformat()
            if isinstance(result.get("file_names"), str):
                result["file_names"] = json.loads(result["file_names"])
        return result

    def delete(self, mindmap_id: int) -> bool:
        sql = "DELETE FROM saved_mindmaps WHERE id = %s"
        affected = self.db.execute(sql, (mindmap_id,))
        logger.info("删除思维导图: id=%d", mindmap_id)
        return affected > 0

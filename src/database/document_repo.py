"""
智能学习助手 — 文档元数据 CRUD
负责: FULL
任务: TASK-DATA-007

管理 MySQL documents 表中的文档元数据记录。
"""

from datetime import datetime

from src.database.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("database.document_repo")


class DocumentRepository:
    """文档元数据 CRUD 操作"""

    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()

    def create_document(
        self,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int = 0,
    ) -> int:
        """
        创建文档记录（状态为 processing）

        Returns:
            文档 ID
        """
        sql = """
            INSERT INTO documents (file_name, file_path, file_type, file_size, status)
            VALUES (%s, %s, %s, %s, 'processing')
        """
        doc_id = self.db.execute_returning_id(
            sql, (file_name, file_path, file_type, file_size)
        )
        logger.info("创建文档记录: id=%d file=%s", doc_id, file_name)
        return doc_id

    def mark_ready(self, doc_id: int, chunks_count: int):
        """标记文档入库完成"""
        sql = "UPDATE documents SET status = 'ready', chunks_count = %s WHERE id = %s"
        self.db.execute(sql, (chunks_count, doc_id))
        logger.info("文档就绪: id=%d chunks=%d", doc_id, chunks_count)

    def mark_error(self, doc_id: int, error_message: str):
        """标记文档处理失败"""
        sql = "UPDATE documents SET status = 'error', error_message = %s WHERE id = %s"
        self.db.execute(sql, (error_message, doc_id))
        logger.error("文档处理失败: id=%d error=%s", doc_id, error_message)

    def get_documents(self, status: str = None, limit: int = 50) -> list:
        """获取文档列表"""
        if status:
            sql = "SELECT * FROM documents WHERE status = %s ORDER BY uploaded_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (status, limit))
        else:
            sql = "SELECT * FROM documents ORDER BY uploaded_at DESC LIMIT %s"
            results = self.db.fetch_all(sql, (limit,))
        for r in results:
            if isinstance(r.get("uploaded_at"), datetime):
                r["uploaded_at"] = r["uploaded_at"].isoformat()
        return results

    def get_document(self, doc_id: int) -> dict:
        """获取单个文档信息"""
        sql = "SELECT * FROM documents WHERE id = %s"
        result = self.db.fetch_one(sql, (doc_id,))
        if result and isinstance(result.get("uploaded_at"), datetime):
            result["uploaded_at"] = result["uploaded_at"].isoformat()
        return result

    def get_total_chunks(self) -> int:
        """获取向量库中总块数（所有 ready 文档的 chunks 之和）"""
        sql = "SELECT COALESCE(SUM(chunks_count), 0) AS total FROM documents WHERE status = 'ready'"
        result = self.db.fetch_one(sql)
        return result["total"] if result else 0

    def get_stats(self) -> dict:
        """获取文档统计信息"""
        sql = """
            SELECT
                COUNT(*) AS total_documents,
                SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS ready_count,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) AS processing_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                COALESCE(SUM(CASE WHEN status = 'ready' THEN chunks_count ELSE 0 END), 0) AS total_chunks
            FROM documents
        """
        return self.db.fetch_one(sql)

    def delete_document(self, doc_id: int) -> bool:
        """删除文档记录"""
        sql = "DELETE FROM documents WHERE id = %s"
        affected = self.db.execute(sql, (doc_id,))
        logger.info("删除文档: id=%d affected=%d", doc_id, affected)
        return affected > 0

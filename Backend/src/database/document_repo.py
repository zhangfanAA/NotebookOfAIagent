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
        user_id: int = None,
    ) -> int:
        """
        创建文档记录（状态为 processing）

        Returns:
            文档 ID
        """
        sql = """
            INSERT INTO documents (file_name, file_path, file_type, file_size, status, user_id)
            VALUES (%s, %s, %s, %s, 'processing', %s)
        """
        doc_id = self.db.execute_returning_id(
            sql, (file_name, file_path, file_type, file_size, user_id)
        )
        logger.info("创建文档记录: id=%d file=%s user_id=%s", doc_id, file_name, user_id)
        return doc_id

    def mark_ready(self, doc_id: int, chunks_count: int):
        """标记文档入库完成"""
        sql = "UPDATE documents SET status = 'ready', chunks_count = %s WHERE id = %s"
        self.db.execute(sql, (chunks_count, doc_id))
        logger.info("文档就绪: id=%d chunks=%d", doc_id, chunks_count)

    def store_full_text(self, doc_id: int, full_text: str):
        """存储文档全文（上传时调用，后续生成思维导图/测验直接读取）"""
        sql = "UPDATE documents SET full_text = %s WHERE id = %s"
        self.db.execute(sql, (full_text, doc_id))
        logger.info("文档全文已存储: id=%d len=%d", doc_id, len(full_text))

    def get_full_text(self, doc_id: int) -> str:
        """获取文档全文"""
        sql = "SELECT full_text FROM documents WHERE id = %s"
        result = self.db.fetch_one(sql, (doc_id,))
        return result["full_text"] if result and result.get("full_text") else ""

    def get_full_text_by_name(self, file_name: str) -> str:
        """根据文件名获取文档全文"""
        sql = "SELECT full_text FROM documents WHERE file_name = %s AND status = 'ready' LIMIT 1"
        result = self.db.fetch_one(sql, (file_name,))
        return result["full_text"] if result and result.get("full_text") else ""

    def mark_error(self, doc_id: int, error_message: str):
        """标记文档处理失败"""
        sql = "UPDATE documents SET status = 'error', error_message = %s WHERE id = %s"
        self.db.execute(sql, (error_message, doc_id))
        logger.error("文档处理失败: id=%d error=%s", doc_id, error_message)

    def get_documents(self, status: str = None, limit: int = 50, user_id: int = None) -> list:
        """获取文档列表"""
        conditions = []
        params = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM documents {where} ORDER BY uploaded_at DESC LIMIT %s"
        params.append(limit)
        results = self.db.fetch_all(sql, tuple(params))
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

    def get_document_by_name(self, file_name: str) -> dict:
        """根据文件名获取文档信息"""
        sql = "SELECT * FROM documents WHERE file_name = %s AND status = 'ready' LIMIT 1"
        return self.db.fetch_one(sql, (file_name,))

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

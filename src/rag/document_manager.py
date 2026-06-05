"""
RAG 文档管理模块
负责: RAG

封装文档上传、删除、统计等操作。
"""

from pathlib import Path

from src.data import vector_store
from src.data.pdf_parser import parse_pdf
from src.data.chunker import chunk_pages
from src.database.document_repo import DocumentRepository
from src.logger import get_logger

logger = get_logger("rag.document_manager")


class DocumentManager:
    """文档管理器"""

    def __init__(self):
        self._doc_repo = DocumentRepository()

    def upload_document(self, file_path: str) -> dict:
        """
        文档上传与入库

        Args:
            file_path: 文件本地路径

        Returns:
            成功: {"status": "success", "chunks_count": int, "message": str}
            失败: {"status": "error", "chunks_count": 0, "message": str}
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "chunks_count": 0, "message": f"文件不存在: {file_path}"}

        file_name = path.name
        file_type = path.suffix.lstrip(".").lower()
        file_size = path.stat().st_size

        # 记录到 MySQL
        doc_id = self._doc_repo.create_document(
            file_name=file_name,
            file_path=str(path),
            file_type=file_type,
            file_size=file_size,
        )

        try:
            # 解析 PDF
            if file_type == "pdf":
                pages = parse_pdf(file_path)
            else:
                return {"status": "error", "chunks_count": 0,
                        "message": f"暂不支持的文件类型: {file_type}"}

            # 分块
            chunks = chunk_pages(pages)
            if not chunks:
                self._doc_repo.mark_error(doc_id, "文档解析后无有效内容")
                return {"status": "error", "chunks_count": 0, "message": "文档无有效内容"}

            # 入库向量库
            count = vector_store.ingest_chunks(chunks)

            # 更新 MySQL
            self._doc_repo.mark_ready(doc_id, count)

            logger.info("文档上传成功: %s → %d chunks", file_name, count)
            return {
                "status": "success",
                "chunks_count": count,
                "message": f"文档 '{file_name}' 入库成功，共 {count} 个知识片段",
            }

        except Exception as e:
            error_msg = str(e)
            self._doc_repo.mark_error(doc_id, error_msg)
            logger.error("文档上传失败: %s — %s", file_name, error_msg)
            return {"status": "error", "chunks_count": 0, "message": error_msg}

    def get_documents(self) -> list:
        """获取文档列表"""
        return self._doc_repo.get_documents()

    def delete_document(self, doc_id: int) -> bool:
        """删除文档（同时删除向量库中的 chunks）"""
        doc = self._doc_repo.get_document(doc_id)
        if not doc:
            return False
        # 删除向量库中的 chunks
        if doc.get("status") == "ready" and doc.get("file_name"):
            try:
                vector_store.delete_by_source(doc["file_name"])
            except Exception as e:
                logger.warning("删除向量库 chunks 失败: %s", str(e))
        # 删除 MySQL 记录
        return self._doc_repo.delete_document(doc_id)

    def get_vector_db_stats(self) -> dict:
        """获取向量库统计信息"""
        try:
            vs_stats = vector_store.get_stats()
            doc_stats = self._doc_repo.get_stats()
            return {
                "total_chunks": vs_stats["total_chunks"],
                "collection_name": vs_stats["collection_name"],
                "total_documents": doc_stats.get("total_documents", 0),
                "ready_documents": doc_stats.get("ready_count", 0),
            }
        except Exception as e:
            logger.error("获取统计信息失败: %s", str(e))
            return {"error": str(e)}

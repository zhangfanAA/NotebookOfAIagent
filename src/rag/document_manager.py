"""
RAG 文档管理模块
负责: RAG

封装文档上传、删除、统计等操作。
"""

import os
import shutil
from pathlib import Path

from src.data import vector_store
from src.data.pdf_parser import parse_pdf
from src.data.chunker import chunk_pages
from src.database.document_repo import DocumentRepository
from src.config import get_config
from src.logger import get_logger

logger = get_logger("rag.document_manager")


def _get_pdf_dir() -> str:
    """PDF 永久存储目录（基于 config.data_dir）"""
    return os.path.join(get_config()["data_dir"], "pdfs")


class DocumentManager:
    """文档管理器"""

    def __init__(self):
        self._doc_repo = DocumentRepository()

    def upload_document(self, file_path: str, original_filename: str = None, user_id: int = None) -> dict:
        """
        文档上传与入库

        Args:
            file_path: 文件本地路径
            original_filename: 用户上传时的原始文件名（中文等），为 None 时从 file_path 提取
            user_id: 用户 ID

        Returns:
            成功: {"status": "success", "chunks_count": int, "message": str}
            失败: {"status": "error", "chunks_count": 0, "message": str}
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "chunks_count": 0, "message": f"文件不存在: {file_path}"}

        file_name = original_filename if original_filename else path.name
        file_type = path.suffix.lstrip(".").lower()
        file_size = path.stat().st_size

        # 复制到永久存储目录
        pdf_dir = _get_pdf_dir()
        os.makedirs(pdf_dir, exist_ok=True)
        permanent_path = os.path.join(pdf_dir, file_name)
        shutil.copy2(str(path), permanent_path)
        logger.info("文件已复制到永久目录: %s", permanent_path)

        # 记录到 MySQL
        doc_id = self._doc_repo.create_document(
            file_name=file_name,
            file_path=permanent_path,
            file_type=file_type,
            file_size=file_size,
            user_id=user_id,
        )

        try:
            # 解析 PDF
            if file_type == "pdf":
                result = parse_pdf(file_path)
                pages = result["pages"]
                ocr_skipped = result.get("ocr_skipped", False)
                ocr_skipped_pages = result.get("ocr_skipped_pages", 0)
            else:
                return {"status": "error", "chunks_count": 0,
                        "message": f"暂不支持的文件类型: {file_type}"}

            # 修正 source 名：parse_pdf 用临时文件名，需要替换为原始文件名
            for page in pages:
                page["source"] = file_name

            # 提取并存储全文（后续生成思维导图/测验直接读取，不再重复解析）
            full_text = "\n\n".join(p["content"] for p in pages if p.get("content"))
            if full_text:
                self._doc_repo.store_full_text(doc_id, full_text)

            # 分块
            chunks = chunk_pages(pages)
            if not chunks:
                self._doc_repo.mark_error(doc_id, "文档解析后无有效内容")
                return {"status": "error", "chunks_count": 0, "message": "文档无有效内容"}

            # 入库向量库（按用户隔离 collection）
            count = vector_store.ingest_chunks(chunks, user_id=user_id)

            # 更新 MySQL
            self._doc_repo.mark_ready(doc_id, count)

            logger.info("文档上传成功: %s → %d chunks", file_name, count)
            response = {
                "status": "success",
                "chunks_count": count,
                "message": f"文档 '{file_name}' 入库成功，共 {count} 个知识片段",
            }
            # 如果有扫描页被跳过，添加提示信息
            if ocr_skipped:
                response["ocr_skipped"] = True
                response["ocr_skipped_pages"] = ocr_skipped_pages
                response["message"] += f"（注意：{ocr_skipped_pages} 页扫描内容因 PaddleOCR 未启用而被跳过）"
            return response

        except Exception as e:
            error_msg = str(e)
            self._doc_repo.mark_error(doc_id, error_msg)
            logger.error("文档上传失败: %s — %s", file_name, error_msg)
            return {"status": "error", "chunks_count": 0, "message": error_msg}

    def get_documents(self, user_id: int = None) -> list:
        """获取文档列表"""
        return self._doc_repo.get_documents(user_id=user_id)

    def delete_document(self, doc_id: int) -> bool:
        """删除文档（同时删除向量库中的 chunks）"""
        doc = self._doc_repo.get_document(doc_id)
        if not doc:
            return False
        # 删除向量库中的 chunks（传入 user_id 以定位正确的 collection）
        if doc.get("status") == "ready" and doc.get("file_name"):
            try:
                vector_store.delete_by_source(doc["file_name"], user_id=doc.get("user_id"))
            except Exception as e:
                logger.warning("删除向量库 chunks 失败: %s", str(e))
        # 删除 MySQL 记录
        return self._doc_repo.delete_document(doc_id)

    def get_vector_db_stats(self, user_id: int = None) -> dict:
        """获取向量库统计信息"""
        try:
            vs_stats = vector_store.get_stats(user_id=user_id)
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

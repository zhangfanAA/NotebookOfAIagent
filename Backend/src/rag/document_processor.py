"""
文档全文提取与 Prompt 组装模块
负责: RAG

从磁盘 PDF 文件提取完整文本（非 RAG 切片），
用于思维导图/笔记生成等需要全局视野的场景。
"""

import os
from pathlib import Path

from src.data.pdf_parser import parse_pdf
from src.database.document_repo import DocumentRepository
from src.config import get_config
from src.logger import get_logger

logger = get_logger("rag.document_processor")


def _get_pdf_dir() -> str:
    """PDF 文件存储目录（基于 config.data_dir）"""
    return os.path.join(get_config()["data_dir"], "pdfs")


class DocumentProcessor:
    """文档全文提取器"""

    def __init__(self):
        self._doc_repo = DocumentRepository()

    def list_available_documents(self) -> list:
        """列出知识库中已就绪的文档（供前端勾选）"""
        docs = self._doc_repo.get_documents()
        return [
            {"file_name": d["file_name"], "id": d["id"], "chunks": d.get("chunks_count", 0)}
            for d in docs
            if d.get("status") == "ready"
        ]

    def get_document_full_text(self, file_names: list) -> dict:
        """
        获取指定文档的完整文本

        优先从数据库读取（上传时已存储），数据库没有时回退到解析 PDF。

        Args:
            file_names: 文件名列表，如 ["第3章.pdf", "第4章.pdf"]

        Returns:
            {文件名: 全文内容}
        """
        result = {}
        for name in file_names:
            # 优先从数据库读取（快速路径）
            full_text = self._doc_repo.get_full_text_by_name(name)
            if full_text:
                result[name] = full_text
                logger.info("从数据库读取全文: %s → %d 字", name, len(full_text))
                continue

            # 回退：从磁盘解析 PDF（兼容旧数据或数据库无全文的情况）
            file_path = os.path.join(_get_pdf_dir(), name)
            if not os.path.exists(file_path):
                logger.warning("文件不存在且数据库无全文: %s", name)
                result[name] = ""
                continue
            try:
                result_pdf = parse_pdf(file_path)
                pages = result_pdf["pages"]
                full_text = "\n\n".join(p["content"] for p in pages if p.get("content"))
                result[name] = full_text
                logger.info("从PDF解析全文（回退）: %s → %d 字", name, len(full_text))
                # 回填到数据库，下次直接读库
                try:
                    doc = self._doc_repo.get_document_by_name(name)
                    if doc:
                        self._doc_repo.store_full_text(doc["id"], full_text)
                        logger.info("已回填全文到数据库: %s", name)
                except Exception as e:
                    logger.warning("回填全文失败: %s — %s", name, str(e))
            except Exception as e:
                logger.error("提取全文失败: %s — %s", name, str(e))
                result[name] = ""
        return result

    def get_total_length(self, file_contents: dict) -> int:
        """计算所有文件总字数"""
        return sum(len(v) for v in file_contents.values())

    def backfill_full_text(self):
        """回填所有缺少全文的旧文档（启动时调用一次）"""
        docs = self._doc_repo.get_documents(status="ready")
        filled = 0
        for doc in docs:
            if doc.get("full_text"):
                continue
            name = doc["file_name"]
            doc_id = doc["id"]
            file_path = os.path.join(_get_pdf_dir(), name)
            if not os.path.exists(file_path):
                logger.warning("回填跳过: 文件不存在 %s", name)
                continue
            try:
                result_pdf = parse_pdf(file_path)
                pages = result_pdf["pages"]
                full_text = "\n\n".join(p["content"] for p in pages if p.get("content"))
                if full_text:
                    self._doc_repo.store_full_text(doc_id, full_text)
                    filled += 1
                    logger.info("回填成功: %s → %d 字", name, len(full_text))
            except Exception as e:
                logger.warning("回填失败: %s — %s", name, str(e))
        if filled:
            logger.info("回填完成: 共补充 %d 篇文档全文", filled)
        return filled

    def build_generation_prompt(self, file_contents: dict, user_prompt: str, output_type: str) -> list:
        """
        组装 LLM 消息列表

        Args:
            file_contents: {文件名: 全文}
            user_prompt: 用户强化提示词
            output_type: "mindmap" 或 "notes"

        Returns:
            LLM messages 列表 [{"role": ..., "content": ...}]
        """
        # 构建文档内容部分
        doc_parts = []
        for name, text in file_contents.items():
            doc_parts.append(f"=== 文件: {name} ===\n{text}")
        all_content = "\n\n".join(doc_parts)

        # 根据输出类型选择 system prompt
        if output_type == "mindmap":
            system_prompt = """你是一个顶尖的学术助教，擅长将复杂的学术文档转化为结构清晰的思维导图。

## 输出要求
1. 必须输出严格的 JSON 数组格式，不要输出其他任何内容
2. JSON 数组中的每个元素代表一个节点，包含以下字段：
   - "id": 节点唯一标识（字符串，如 "1", "2", "3"）
   - "label": 节点显示文字（中文，简洁不超过15个字）
   - "parentId": 父节点ID（根节点为 null）
3. 树形结构：根节点的 parentId 为 null，其他节点通过 parentId 建立层级关系
4. 层级不超过 4 层，节点数量不超过 25 个
5. 使用中文

## 输出示例
```json
[
  {"id": "1", "label": "C语言核心", "parentId": null},
  {"id": "2", "label": "指针与内存", "parentId": "1"},
  {"id": "3", "label": "结构体", "parentId": "1"},
  {"id": "4", "label": "指针基础", "parentId": "2"},
  {"id": "5", "label": "内存管理", "parentId": "2"}
]
```

只输出 JSON 数组，不要输出任何其他文字或代码块标记。"""
        else:
            system_prompt = """你是一个顶尖的学术助教，擅长将复杂的学术文档转化为结构清晰的重点笔记。

## 输出要求
1. 使用 Markdown 格式输出
2. 一级标题为文档主题
3. 二级标题为主要知识点分类
4. 三级标题为子知识点
5. 使用要点列表（-）列举关键内容
6. 重要内容用 **加粗** 标注
7. 适当使用表格对比相似概念
8. 使用中文
9. 结构清晰，重点突出，适合复习使用"""

        # 用户提示词
        user_parts = []
        if user_prompt.strip():
            user_parts.append(f"## 用户特别要求（最高优先级）\n{user_prompt.strip()}")
        user_parts.append(f"## 文档内容\n{all_content}")
        user_content = "\n\n".join(user_parts)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

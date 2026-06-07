"""
文档对比模块
负责: RAG

调用 LLM 对比两个文档的异同点。
"""

from src.rag.document_processor import DocumentProcessor
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.compare_generator")


class CompareGenerator:
    """文档对比生成器"""

    def __init__(self):
        self._processor = DocumentProcessor()
        self._llm = LLMClient()

    def generate(self, file_names: list, focus: str = "") -> dict:
        """
        对比文档

        Args:
            file_names: 文件名列表（需要恰好 2 个）
            focus: 对比聚焦点（可选）

        Returns:
            {"status": "success"|"error", "content": str, "message": str}
        """
        if len(file_names) < 2:
            return {"status": "error", "content": "", "message": "请至少选择两个文件进行对比"}

        try:
            logger.info("开始文档对比，文件: %s", file_names)
            file_contents = self._processor.get_document_full_text(file_names)
            valid_contents = {k: v for k, v in file_contents.items() if v.strip()}
            if len(valid_contents) < 2:
                return {"status": "error", "content": "", "message": "至少需要两个有效文件"}

            # 截取前 15000 字/文件
            truncated = {}
            for name, text in valid_contents.items():
                truncated[name] = text[:15000]

            prompt = self._build_prompt(truncated, focus)
            answer = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096,
            )

            logger.info("文档对比完成，输出长度: %d", len(answer))
            return {
                "status": "success",
                "content": answer,
                "message": "对比分析完成",
            }

        except Exception as e:
            logger.error("文档对比失败: %s", str(e))
            return {"status": "error", "content": "", "message": str(e)}

    def _build_prompt(self, file_contents: dict, focus: str) -> str:
        """构建 prompt"""
        doc_parts = []
        for name, text in file_contents.items():
            doc_parts.append(f"=== {name} ===\n{text[:15000]}")

        focus_part = f"\n\n## 对比聚焦点\n{focus}" if focus.strip() else ""

        return f"""你是一个学术助教。请对比分析以下文档的异同点。

## 要求
1. 使用 Markdown 格式输出
2. 列出共同知识点
3. 列出各自独有的知识点
4. 用表格对比关键概念的差异
5. 总结两份文档的关系（互补/重叠/递进）
6. 使用中文
{focus_part}

## 文档内容
{" ".join(doc_parts)}"""

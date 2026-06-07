"""
思维导图/笔记生成模块
负责: RAG

调用 LLM 将文档内容转化为 JSON 思维导图或结构化笔记。
"""

import re
import json

from src.rag.document_processor import DocumentProcessor
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.mindmap_generator")

# 单文件上下文阈值（字符数），超过此值需要 Map-Reduce
CONTEXT_THRESHOLD = 60000


class MindmapGenerator:
    """思维导图/笔记生成器"""

    def __init__(self):
        self._processor = DocumentProcessor()
        self._llm = LLMClient()

    def list_documents(self) -> list:
        """列出可选文档"""
        return self._processor.list_available_documents()

    def generate(self, file_names: list, user_prompt: str = "", output_type: str = "mindmap") -> dict:
        """
        生成思维导图或笔记

        Args:
            file_names: 选中的文件名列表
            user_prompt: 用户强化提示词
            output_type: "mindmap" 或 "notes"

        Returns:
            {
                "status": "success"|"error",
                "type": "mindmap"|"notes",
                "content": str,          # 完整 LLM 输出（JSON 格式或 Markdown）
                "nodes": list|None,      # 解析后的节点列表（仅导图）
                "message": str,
            }
        """
        if not file_names:
            return {"status": "error", "type": output_type, "content": "", "nodes": None, "mermaid_code": None, "message": "请至少选择一个文件"}

        try:
            # 1. 提取全文
            logger.info("开始生成 %s，文件: %s", output_type, file_names)
            file_contents = self._processor.get_document_full_text(file_names)

            # 过滤空文件
            valid_contents = {k: v for k, v in file_contents.items() if v.strip()}
            if not valid_contents:
                return {"status": "error", "type": output_type, "content": "", "nodes": None, "mermaid_code": None, "message": "所选文件无法提取有效内容"}

            # 2. 检查上下文长度，必要时 Map-Reduce
            total_len = self._processor.get_total_length(valid_contents)
            if total_len > CONTEXT_THRESHOLD:
                logger.info("文档总长度 %d 超过阈值，启用 Map-Reduce", total_len)
                llm_messages = self._map_reduce(valid_contents, user_prompt, output_type)
            else:
                llm_messages = self._processor.build_generation_prompt(valid_contents, user_prompt, output_type)

            # 3. 调用 LLM
            logger.info("调用 LLM 生成 %s（%d 字输入）", output_type, total_len)
            answer = self._llm.chat(messages=llm_messages, temperature=0.3, max_tokens=4096)

            # 4. 解析结果
            nodes = None
            mermaid_code = None
            if output_type == "mindmap":
                nodes = self._extract_json_nodes(answer)
                if nodes:
                    mermaid_code = self._nodes_to_mermaid(nodes)

            logger.info("生成完成: type=%s, content_len=%d, has_nodes=%s, has_mermaid=%s",
                        output_type, len(answer), nodes is not None, mermaid_code is not None)

            return {
                "status": "success",
                "type": output_type,
                "content": answer,
                "nodes": nodes,
                "mermaid_code": mermaid_code,
                "message": "生成成功",
            }

        except Exception as e:
            logger.error("生成失败: %s", str(e))
            return {"status": "error", "type": output_type, "content": "", "nodes": None, "mermaid_code": None, "message": str(e)}

    def _extract_json_nodes(self, text: str) -> list:
        """从 LLM 输出中提取 JSON 节点数组"""
        try:
            # 尝试直接解析整个文本
            nodes = json.loads(text)
            if isinstance(nodes, list) and len(nodes) > 0:
                # 验证节点格式
                for node in nodes:
                    if not all(key in node for key in ["id", "label", "parentId"]):
                        logger.warning("节点格式不完整: %s", node)
                        return None
                return nodes
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取 JSON
        match = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
        if match:
            try:
                nodes = json.loads(match.group(1).strip())
                if isinstance(nodes, list) and len(nodes) > 0:
                    for node in nodes:
                        if not all(key in node for key in ["id", "label", "parentId"]):
                            logger.warning("节点格式不完整: %s", node)
                            return None
                    return nodes
            except json.JSONDecodeError:
                pass

        # 尝试提取 JSON 数组（可能被其他文字包围）
        match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
        if match:
            try:
                nodes = json.loads(match.group(0))
                if isinstance(nodes, list) and len(nodes) > 0:
                    for node in nodes:
                        if not all(key in node for key in ["id", "label", "parentId"]):
                            logger.warning("节点格式不完整: %s", node)
                            return None
                    return nodes
            except json.JSONDecodeError:
                pass

        logger.warning("无法从 LLM 输出中提取有效的 JSON 节点数组")
        return None

    def _nodes_to_mermaid(self, nodes: list) -> str:
        """
        将 JSON 节点数组转换为 Mermaid graph LR 语法

        Args:
            nodes: [{"id": "1", "label": "根节点", "parentId": null}, ...]

        Returns:
            Mermaid graph LR 字符串
        """
        if not nodes:
            return ""

        lines = ["graph LR"]

        for node in nodes:
            node_id = str(node.get("id", ""))
            label = node.get("label", "").strip()
            if not node_id or not label:
                continue
            # 转义 Mermaid 特殊字符
            safe_label = label.replace('"', "'").replace("(", "（").replace(")", "）")
            lines.append(f'    {node_id}["{safe_label}"]')

        for node in nodes:
            parent_id = node.get("parentId")
            if parent_id is not None:
                child_id = str(node.get("id", ""))
                lines.append(f"    {parent_id} --> {child_id}")

        return "\n".join(lines)

    def _map_reduce(self, file_contents: dict, user_prompt: str, output_type: str) -> list:
        """
        Map-Reduce 策略处理超长文档

        Map: 分别对每个文件生成摘要
        Reduce: 合并摘要生成最终导图/笔记
        """
        # Map 阶段：分别总结每个文件
        summaries = []
        for name, text in file_contents.items():
            map_prompt = f"请用 500 字以内概括以下文档的核心知识点：\n\n=== {name} ===\n{text}"
            try:
                summary = self._llm.chat(
                    messages=[{"role": "user", "content": map_prompt}],
                    temperature=0.2,
                    max_tokens=1024,
                )
                summaries.append(f"## {name}\n{summary}")
            except Exception as e:
                logger.warning("Map 阶段失败: %s — %s", name, str(e))

        if not summaries:
            raise RuntimeError("所有文件的摘要生成均失败")

        # Reduce 阶段：用摘要生成最终输出
        combined = "\n\n".join(summaries)
        return self._processor.build_generation_prompt(
            {"文档摘要": combined}, user_prompt, output_type
        )

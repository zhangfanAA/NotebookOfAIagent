"""
闪卡生成模块
负责: RAG

调用 LLM 根据文档内容生成问答对闪卡。
"""

import re
import json

from src.rag.document_processor import DocumentProcessor
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.flashcard_generator")


class FlashcardGenerator:
    """闪卡生成器"""

    def __init__(self):
        self._processor = DocumentProcessor()
        self._llm = LLMClient()

    def generate(self, file_names: list, num_cards: int = 10, topic_focus: str = "") -> dict:
        """
        生成闪卡

        Args:
            file_names: 选中的文件名列表
            num_cards: 闪卡数量
            topic_focus: 主题聚焦（可选）

        Returns:
            {"status": "success"|"error", "cards": list, "message": str}
        """
        if not file_names:
            return {"status": "error", "cards": [], "message": "请至少选择一个文件"}

        try:
            logger.info("开始生成闪卡，文件: %s，数量: %d", file_names, num_cards)
            file_contents = self._processor.get_document_full_text(file_names)
            valid_contents = {k: v for k, v in file_contents.items() if v.strip()}
            if not valid_contents:
                return {"status": "error", "cards": [], "message": "所选文件无法提取有效内容"}

            truncated = {}
            remaining = 30000
            for name, text in valid_contents.items():
                if remaining <= 0:
                    break
                truncated[name] = text[:remaining]
                remaining -= len(text)

            prompt = self._build_prompt(truncated, num_cards, topic_focus)
            answer = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=4096,
            )

            cards = self._parse_cards(answer)
            logger.info("闪卡生成完成: %d 张", len(cards))

            return {
                "status": "success",
                "cards": cards,
                "message": f"成功生成 {len(cards)} 张闪卡",
            }

        except Exception as e:
            logger.error("闪卡生成失败: %s", str(e))
            return {"status": "error", "cards": [], "message": str(e)}

    def _build_prompt(self, file_contents: dict, num_cards: int, topic_focus: str) -> str:
        """构建 prompt"""
        doc_parts = []
        for name, text in file_contents.items():
            doc_parts.append(f"=== {name} ===\n{text}")
        all_content = "\n\n".join(doc_parts)

        focus_part = f"\n8. 重点关注主题：{topic_focus}" if topic_focus.strip() else ""

        return f"""你是一个学术助教。根据以下文档内容生成闪卡（问答对），用于学生复习记忆。

## 要求
1. 生成 {num_cards} 张闪卡
2. 每张闪卡包含：正面（问题）和背面（答案）
3. 问题简洁明确，答案精炼准确
4. 覆盖文档中的关键知识点
5. 使用中文
{focus_part}
6. 必须严格按以下 JSON 格式输出，不要输出其他内容：

```json
[
  {{
    "front": "问题内容",
    "back": "答案内容",
    "category": "知识点分类"
  }}
]
```

## 文档内容
{all_content}"""

    def _parse_cards(self, text: str) -> list:
        """从 LLM 输出中解析闪卡 JSON"""
        match = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
        else:
            match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                logger.warning("无法解析闪卡 JSON")
                return []

        try:
            cards = json.loads(json_str)
            valid = []
            for c in cards:
                if "front" in c and "back" in c:
                    valid.append(c)
            return valid
        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败: %s", str(e))
            return []

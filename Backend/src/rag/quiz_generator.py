"""
智能出题模块
负责: RAG

调用 LLM 根据文档内容生成测验题目（选择题/填空题/简答题）。
"""

import re
import json

from src.rag.document_processor import DocumentProcessor
from src.rag.llm_client import LLMClient
from src.logger import get_logger

logger = get_logger("rag.quiz_generator")


class QuizGenerator:
    """智能出题器"""

    def __init__(self):
        self._processor = DocumentProcessor()
        self._llm = LLMClient()

    def generate(self, file_names: list, num_questions: int = 5, difficulty: str = "medium", qtypes: list = None) -> dict:
        """
        生成测验题目

        Args:
            file_names: 选中的文件名列表
            num_questions: 题目数量
            difficulty: easy / medium / hard
            qtypes: 题型列表，如 ["choice", "fill", "short_answer"]

        Returns:
            {"status": "success"|"error", "questions": list, "message": str}
        """
        if not file_names:
            return {"status": "error", "questions": [], "message": "请至少选择一个文件"}

        if qtypes is None:
            qtypes = ["choice", "fill", "short_answer"]

        try:
            logger.info("开始生成测验，文件: %s，题数: %d，难度: %s", file_names, num_questions, difficulty)
            file_contents = self._processor.get_document_full_text(file_names)
            valid_contents = {k: v for k, v in file_contents.items() if v.strip()}
            if not valid_contents:
                return {"status": "error", "questions": [], "message": "所选文件无法提取有效内容"}

            total_len = self._processor.get_total_length(valid_contents)
            # 截取前 30000 字避免超长
            truncated = {}
            remaining = 30000
            for name, text in valid_contents.items():
                if remaining <= 0:
                    break
                truncated[name] = text[:remaining]
                remaining -= len(text)

            prompt = self._build_prompt(truncated, num_questions, difficulty, qtypes)
            answer = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=4096,
            )

            questions = self._parse_questions(answer)
            logger.info("生成完成: %d 道题目", len(questions))

            return {
                "status": "success",
                "questions": questions,
                "message": f"成功生成 {len(questions)} 道题目",
            }

        except Exception as e:
            logger.error("测验生成失败: %s", str(e))
            return {"status": "error", "questions": [], "message": str(e)}

    def check_answer(self, question: dict, user_answer: str) -> dict:
        """
        判分

        Args:
            question: 题目 dict
            user_answer: 用户答案

        Returns:
            {"correct": bool, "explanation": str}
        """
        qtype = question.get("type", "short_answer")
        correct_answer = question.get("answer", "")

        if qtype == "choice":
            # 提取选项字母（兼容 "B" 和 "B. 选项内容" 两种格式）
            def extract_letter(s: str) -> str:
                s = s.strip()
                m = re.match(r'^([A-Da-d])', s)
                return m.group(1).upper() if m else s.upper()
            is_correct = extract_letter(user_answer) == extract_letter(correct_answer)
        elif qtype == "fill":
            # 填空题：忽略空白差异
            is_correct = user_answer.strip() == correct_answer.strip()
        else:
            # 简答题：用 LLM 判分
            is_correct = self._llm_check(question.get("question", ""), correct_answer, user_answer)

        return {
            "correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": question.get("explanation", ""),
        }

    def _llm_check(self, question: str, reference: str, user_answer: str) -> bool:
        """用 LLM 判断简答题是否正确"""
        prompt = f"""判断用户的回答是否正确。

题目：{question}
参考答案：{reference}
用户回答：{user_answer}

只回复 "正确" 或 "错误"，不要回复其他内容。"""
        try:
            result = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            return "正确" in result
        except Exception:
            return False

    def _build_prompt(self, file_contents: dict, num_questions: int, difficulty: str, qtypes: list) -> str:
        """构建出题 prompt"""
        doc_parts = []
        for name, text in file_contents.items():
            doc_parts.append(f"=== {name} ===\n{text}")
        all_content = "\n\n".join(doc_parts)

        type_names = {"choice": "选择题", "fill": "填空题", "short_answer": "简答题"}
        type_str = "、".join(type_names.get(t, t) for t in qtypes)

        difficulty_desc = {"easy": "基础", "medium": "中等", "hard": "困难"}

        return f"""你是一个专业的学术出题助手。根据以下文档内容生成测验题目。

## 要求
1. 生成 {num_questions} 道题目
2. 题型：{type_str}，均匀分布
3. 难度：{difficulty_desc.get(difficulty, "中等")}
4. 使用中文
5. 必须严格按以下 JSON 格式输出，不要输出其他内容：

```json
[
  {{
    "type": "choice",
    "question": "题目内容",
    "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
    "answer": "A",
    "explanation": "解析说明"
  }},
  {{
    "type": "fill",
    "question": "题目内容，用 ___ 表示空格",
    "answer": "正确答案",
    "explanation": "解析说明"
  }},
  {{
    "type": "short_answer",
    "question": "题目内容",
    "answer": "参考答案",
    "explanation": "解析说明"
  }}
]
```

## 文档内容
{all_content}"""

    def _parse_questions(self, text: str) -> list:
        """从 LLM 输出中解析题目 JSON"""
        # 尝试提取 ```json ... ``` 代码块
        match = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
        else:
            # 尝试直接解析整个文本中的 JSON 数组
            match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                logger.warning("无法解析题目 JSON")
                return []

        try:
            questions = json.loads(json_str)
            # 验证结构
            valid = []
            for q in questions:
                if "question" in q and "answer" in q and "type" in q:
                    valid.append(q)
            return valid
        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败: %s", str(e))
            return []

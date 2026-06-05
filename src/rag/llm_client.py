"""
智能学习助手 — LLM 统一调用客户端
负责: RAG
任务: TASK-AGENT-007

封装 Ollama 本地模型（主）和 DeepSeek API（备）的统一调用接口。
支持自动降级：Ollama 不可用时自动切换到 DeepSeek API。
"""

import time
from typing import Optional

import ollama
from openai import OpenAI

from src.config import get_config
from src.logger import get_logger

logger = get_logger("rag.llm_client")


class LLMClient:
    """
    LLM 统一调用客户端

    调用策略:
    1. 优先使用 Ollama 本地模型
    2. Ollama 不可用时（连接失败/超时），自动降级到 DeepSeek API
    3. 可通过 use_fallback=True 强制使用 DeepSeek

    Usage:
        client = LLMClient()
        response = client.chat([{"role": "user", "content": "你好"}])
    """

    def __init__(self, config: dict = None):
        """
        初始化主模型（Ollama）和备选模型（DeepSeek API）

        Args:
            config: llm 配置段，为 None 时从全局配置读取
        """
        if config is None:
            config = get_config()["llm"]

        # Ollama 配置
        self._ollama_config = config["primary"]
        self._ollama_client = ollama.Client(
            host=self._ollama_config["base_url"],
            timeout=self._ollama_config.get("timeout", 30),
        )
        self._ollama_model = self._ollama_config["model"]

        # DeepSeek API 配置（OpenAI 兼容格式）
        self._deepseek_config = config["fallback"]
        self._deepseek_client = None
        self._deepseek_model = self._deepseek_config["model"]

        api_key = self._deepseek_config.get("api_key", "")
        if api_key:
            self._deepseek_client = OpenAI(
                api_key=api_key,
                base_url=self._deepseek_config["base_url"],
                timeout=self._deepseek_config.get("timeout", 30),
            )
            logger.info("DeepSeek API 客户端已初始化: model=%s", self._deepseek_model)
        else:
            logger.warning("DeepSeek API Key 未配置，云端降级不可用")

        logger.info(
            "LLMClient 初始化完成: primary=%s, fallback=%s",
            self._ollama_model,
            self._deepseek_model if self._deepseek_client else "不可用",
        )

    def is_ollama_available(self) -> bool:
        """检测 Ollama 服务是否在线"""
        try:
            self._ollama_client.list()
            return True
        except Exception:
            return False

    def chat(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        use_fallback: bool = False,
    ) -> str:
        """
        标准对话调用

        调用策略:
        - use_fallback=True → 直接使用 DeepSeek API
        - 否则先尝试 Ollama，失败后自动降级到 DeepSeek

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": str}]
            temperature: 温度参数（评估节点建议 0，生成节点建议 0.3）
            max_tokens: 最大生成 token 数
            use_fallback: 是否强制使用 DeepSeek API

        Returns:
            模型输出字符串

        Raises:
            RuntimeError: 两个模型都调用失败时抛出
        """
        if use_fallback:
            return self._call_deepseek(messages, temperature, max_tokens)

        # 先尝试 Ollama
        try:
            return self._call_ollama(messages, temperature, max_tokens)
        except Exception as e:
            logger.warning("Ollama 调用失败: %s，尝试 DeepSeek API 降级", str(e))
            return self._call_deepseek(messages, temperature, max_tokens)

    def chat_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        """
        流式对话调用（生成器）

        逐 token 返回结果，用于前端实时显示。

        Yields:
            str: 每个 token 的文本片段
        """
        # 优先 Ollama 流式
        try:
            stream = self._ollama_client.chat(
                model=self._ollama_model,
                messages=messages,
                options={"temperature": temperature, "num_predict": max_tokens},
                stream=True,
            )
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
            return
        except Exception as e:
            logger.warning("Ollama 流式调用失败: %s，尝试 DeepSeek", str(e))

        # DeepSeek 流式降级
        if not self._deepseek_client:
            # 兜底：非流式调用
            result = self.chat(messages, temperature, max_tokens)
            yield result
            return

        try:
            stream = self._deepseek_client.chat.completions.create(
                model=self._deepseek_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error("DeepSeek 流式调用也失败: %s", str(e))
            result = self.chat(messages, temperature, max_tokens, use_fallback=True)
            yield result

    def _call_ollama(self, messages: list, temperature: float, max_tokens: int) -> str:
        """调用 Ollama 本地模型"""
        start = time.time()
        response = self._ollama_client.chat(
            model=self._ollama_model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )
        elapsed = time.time() - start
        content = response["message"]["content"]
        logger.debug("Ollama 响应: %.2fs, %d tokens", elapsed, len(content))
        return content

    def _call_deepseek(self, messages: list, temperature: float, max_tokens: int, retries: int = 3) -> str:
        """调用 DeepSeek API（OpenAI 兼容格式，带重试）"""
        if not self._deepseek_client:
            raise RuntimeError(
                "DeepSeek API 不可用: 未配置 API Key。"
                "请在 .env 文件中设置 DEEPSEEK_API_KEY"
            )

        last_error = None
        for attempt in range(retries):
            try:
                start = time.time()
                response = self._deepseek_client.chat.completions.create(
                    model=self._deepseek_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed = time.time() - start
                content = response.choices[0].message.content
                logger.debug("DeepSeek API 响应: %.2fs, %d chars", elapsed, len(content))
                return content
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning("DeepSeek API 调用失败 (尝试 %d/%d): %s，%ds 后重试", attempt + 1, retries, str(e), wait)
                    time.sleep(wait)

        raise RuntimeError(f"DeepSeek API 调用失败（已重试 {retries} 次）: {last_error}")

    def vision(self, image_path: str, prompt: str) -> str:
        """
        多模态调用（图片文字/公式提取）

        优先使用 Ollama Qwen-VL，降级时用 DeepSeek vision。

        Args:
            image_path: 图片本地路径
            prompt: 提取指令，如 "请提取图片中的文字和公式"

        Returns:
            提取出的文字内容
        """
        import base64
        from pathlib import Path

        image_data = Path(image_path).read_bytes()
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # 先尝试 Ollama Qwen-VL
        try:
            response = self._ollama_client.chat(
                model="qwen2.5-vl:7b",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_b64],
                    }
                ],
            )
            return response["message"]["content"]
        except Exception as e:
            logger.warning("Ollama 多模态调用失败: %s", str(e))

        # DeepSeek 降级（如果支持 vision）
        if self._deepseek_client:
            try:
                response = self._deepseek_client.chat.completions.create(
                    model=self._deepseek_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_b64}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error("DeepSeek vision 调用也失败: %s", str(e))

        raise RuntimeError("所有多模态模型调用均失败")

"""
智能学习助手 — LLM 统一调用客户端
负责: RAG
任务: TASK-AGENT-007

封装 Ollama 本地模型（主）和 DeepSeek API（备）的统一调用接口。
支持通过数据库设置动态切换本地/云端模型。
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
    - provider=local  → 只用 Ollama
    - provider=cloud  → 只用云端 API（OpenAI 兼容格式）
    - 默认从数据库 settings 表读取 provider

    Usage:
        client = LLMClient()
        response = client.chat([{"role": "user", "content": "你好"}])
    """

    def __init__(self, config: dict = None):
        """
        初始化 LLM 客户端

        Args:
            config: llm 配置段，为 None 时从全局配置读取
        """
        if config is None:
            config = get_config()["llm"]

        self._config = config

        # Ollama 配置
        self._ollama_config = config["primary"]
        self._ollama_client = ollama.Client(
            host=self._ollama_config["base_url"],
            timeout=self._ollama_config.get("timeout", 30),
        )
        self._ollama_model = self._ollama_config["model"]

        # 云端 API 配置（OpenAI 兼容格式）
        self._cloud_config = config["fallback"]
        self._cloud_client = None
        self._cloud_model = self._cloud_config["model"]

        # 从数据库读取当前 provider 设置
        self._provider = self._read_provider_from_db()

        # 初始化云端客户端（如果配置了 API Key）
        self._init_cloud_client()

        logger.info(
            "LLMClient 初始化完成: provider=%s, local_model=%s, cloud_model=%s",
            self._provider,
            self._ollama_model,
            self._cloud_model if self._cloud_client else "不可用",
        )

    def _read_provider_from_db(self) -> str:
        """从数据库读取当前 LLM provider 设置"""
        try:
            from src.database.settings_repo import SettingsRepository
            repo = SettingsRepository()
            provider = repo.get("llm_provider")
            if provider in ("local", "cloud"):
                # 同时读取云端配置覆盖
                cloud_url = repo.get("cloud_base_url")
                cloud_key = repo.get("cloud_api_key")
                cloud_model = repo.get("cloud_model")
                if cloud_url:
                    self._cloud_config["base_url"] = cloud_url
                if cloud_key:
                    self._cloud_config["api_key"] = cloud_key
                if cloud_model:
                    self._cloud_model = cloud_model
                    self._cloud_config["model"] = cloud_model
                return provider
        except Exception as e:
            logger.debug("读取 LLM 设置失败，使用默认: %s", str(e))
        return "local"

    def _init_cloud_client(self):
        """初始化云端 API 客户端"""
        api_key = self._cloud_config.get("api_key", "")
        if api_key:
            self._cloud_client = OpenAI(
                api_key=api_key,
                base_url=self._cloud_config["base_url"],
                timeout=self._cloud_config.get("timeout", 30),
            )
            logger.info("云端 API 客户端已初始化: model=%s, base_url=%s", self._cloud_model, self._cloud_config["base_url"])
        else:
            logger.warning("云端 API Key 未配置")

    @property
    def provider(self) -> str:
        return self._provider

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

        根据 provider 设置决定调用本地或云端模型。

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": str}]
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            use_backward_compat: 兼容旧代码，不再使用

        Returns:
            模型输出字符串

        Raises:
            RuntimeError: 调用失败时抛出
        """
        if self._provider == "cloud":
            return self._call_cloud(messages, temperature, max_tokens)
        else:
            return self._call_ollama(messages, temperature, max_tokens)

    def chat_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        """
        流式对话调用（生成器）

        根据 provider 设置决定调用本地或云端模型。

        Yields:
            str: 每个 token 的文本片段
        """
        if self._provider == "cloud":
            yield from self._stream_cloud(messages, temperature, max_tokens)
        else:
            yield from self._stream_ollama(messages, temperature, max_tokens)

    def _stream_ollama(self, messages, temperature, max_tokens):
        """Ollama 流式调用"""
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
        except Exception as e:
            logger.error("Ollama 流式调用失败: %s", str(e))
            raise RuntimeError(f"Ollama 流式调用失败: {e}")

    def _stream_cloud(self, messages, temperature, max_tokens):
        """云端 API 流式调用"""
        if not self._cloud_client:
            raise RuntimeError("云端 API 不可用: 未配置 API Key")
        try:
            stream = self._cloud_client.chat.completions.create(
                model=self._cloud_model,
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
            logger.error("云端 API 流式调用失败: %s", str(e))
            raise RuntimeError(f"云端 API 流式调用失败: {e}")

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

    def _call_cloud(self, messages: list, temperature: float, max_tokens: int, retries: int = 3) -> str:
        """调用云端 API（OpenAI 兼容格式，带重试）"""
        if not self._cloud_client:
            raise RuntimeError(
                "云端 API 不可用: 未配置 API Key。请在设置中填入 API Key"
            )

        last_error = None
        for attempt in range(retries):
            try:
                start = time.time()
                response = self._cloud_client.chat.completions.create(
                    model=self._cloud_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed = time.time() - start
                content = response.choices[0].message.content
                logger.debug("云端 API 响应: %.2fs, %d chars", elapsed, len(content))
                return content
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning("云端 API 调用失败 (尝试 %d/%d): %s，%ds 后重试", attempt + 1, retries, str(e), wait)
                    time.sleep(wait)

        raise RuntimeError(f"云端 API 调用失败（已重试 {retries} 次）: {last_error}")

    def vision(self, image_path: str, prompt: str) -> str:
        """
        多模态调用（图片文字/公式提取）

        优先使用 Ollama Qwen-VL，降级时用云端 vision。

        Args:
            image_path: 图片本地路径
            prompt: 提取指令

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

        # 云端降级
        if self._cloud_client:
            try:
                response = self._cloud_client.chat.completions.create(
                    model=self._cloud_model,
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
                logger.error("云端 vision 调用也失败: %s", str(e))

        raise RuntimeError("所有多模态模型调用均失败")

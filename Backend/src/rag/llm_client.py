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

# LLMClient 实例缓存 {user_id: (client, created_at)}
_client_cache: dict[int, tuple] = {}
_CLIENT_CACHE_TTL = 300  # 5 分钟过期


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

    # DeepSeek 定价 (1.1 倍官方价格，单位: 元/百万 tokens)
    PRICING = {
        "deepseek-v4-flash": {"cache_hit": 0.022, "cache_miss": 1.1, "output": 2.2},
        "deepseek-chat":     {"cache_hit": 0.022, "cache_miss": 1.1, "output": 2.2},
        "deepseek-v4-pro":   {"cache_hit": 0.0275, "cache_miss": 3.3, "output": 6.6},
        "deepseek-reasoner": {"cache_hit": 0.0275, "cache_miss": 3.3, "output": 6.6},
    }

    def __init__(self, config: dict = None):
        """
        初始化 LLM 客户端

        Args:
            config: llm 配置段，为 None 时从全局配置读取
        """
        if config is None:
            config = get_config()["llm"]

        self._config = config

        # 上次调用的 token 用量信息
        self.last_usage: dict = None

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

    @classmethod
    def for_user(cls, user_id: int) -> "LLMClient":
        """
        根据用户 ID 创建或复用 LLMClient（带缓存，避免每次请求重建）。
        """
        now = time.time()
        cached = _client_cache.get(user_id)
        if cached:
            client, created_at = cached
            if now - created_at < _CLIENT_CACHE_TTL:
                return client

        client = cls()

        # 全局 provider 为 balance 时，所有用户都走余额模型
        if client._provider == "balance":
            logger.info("LLMClient.for_user(%d): 使用余额模型, model=%s", user_id, client._cloud_model)
            _client_cache[user_id] = (client, now)
            return client

        # 全局 provider 为 cloud 时，检查用户是否有自己的 key
        if client._provider == "cloud":
            try:
                from src.database.user_repo import UserRepository
                user_settings = UserRepository().get_user_api_settings(user_id)
                if user_settings and user_settings.get("cloud_api_key"):
                    api_key = user_settings["cloud_api_key"]
                    base_url = user_settings.get("cloud_base_url") or client._cloud_config.get("base_url")
                    model = user_settings.get("cloud_model") or client._cloud_model

                    client._cloud_config["api_key"] = api_key
                    client._cloud_config["base_url"] = base_url
                    client._cloud_model = model
                    client._cloud_config["model"] = model
                    client._init_cloud_client()
                    logger.info("LLMClient.for_user(%d): 使用用户私有 API Key, model=%s", user_id, model)
            except Exception as e:
                logger.warning("LLMClient.for_user(%d): 读取用户设置失败: %s", user_id, str(e))

        _client_cache[user_id] = (client, now)
        return client

    def _read_provider_from_db(self) -> str:
        """从数据库 global_config 表读取当前 LLM provider 设置"""
        try:
            from src.database.global_config_repo import GlobalConfigRepository
            repo = GlobalConfigRepository()
            cfg = repo.get(1)  # num=1 全局云端配置
            provider = cfg.get("llm_provider") or "local"

            if provider == "balance":
                # 余额模型：使用 num=2 的独立配置
                balance_cfg = repo.get(2)
                balance_key = balance_cfg.get("api_key")
                balance_url = balance_cfg.get("base_url")
                balance_model = balance_cfg.get("model")
                if balance_key:
                    self._cloud_config["api_key"] = balance_key
                if balance_url:
                    self._cloud_config["base_url"] = balance_url
                if balance_model:
                    self._cloud_model = balance_model
                    self._cloud_config["model"] = balance_model
                return "balance"

            if provider == "cloud":
                # 全局云端：使用 num=1 的配置（api_key 为空则用 settings.yaml 默认值）
                cloud_url = cfg.get("base_url")
                cloud_key = cfg.get("api_key")
                cloud_model = cfg.get("model")
                if cloud_url:
                    self._cloud_config["base_url"] = cloud_url
                if cloud_key:
                    self._cloud_config["api_key"] = cloud_key
                if cloud_model:
                    self._cloud_model = cloud_model
                    self._cloud_config["model"] = cloud_model
                return "cloud"

        except Exception as e:
            logger.debug("读取全局 LLM 设置失败，使用默认: %s", str(e))
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

    @staticmethod
    def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int,
                       cache_hit_tokens: int = 0) -> float:
        """
        计算 API 调用费用（元）

        Args:
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            cache_hit_tokens: 缓存命中 token 数

        Returns:
            费用（元）
        """
        # 匹配定价表（模糊匹配，去掉前缀）
        pricing = None
        for key, p in LLMClient.PRICING.items():
            if key in model:
                pricing = p
                break
        if not pricing:
            # 未知模型按 deepseek-chat 定价
            pricing = LLMClient.PRICING["deepseek-chat"]

        cache_miss_tokens = prompt_tokens - cache_hit_tokens
        cost = (
            cache_hit_tokens * pricing["cache_hit"] / 1_000_000
            + cache_miss_tokens * pricing["cache_miss"] / 1_000_000
            + completion_tokens * pricing["output"] / 1_000_000
        )
        return round(cost, 6)

    def chat(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: int = 4096,
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
        if self._provider in ("cloud", "balance"):
            return self._call_cloud(messages, temperature, max_tokens)
        else:
            return self._call_ollama(messages, temperature, max_tokens)

    def chat_stream(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        """
        流式对话调用（生成器）

        根据 provider 设置决定调用本地或云端模型。

        Yields:
            str: 每个 token 的文本片段
        """
        if self._provider in ("cloud", "balance"):
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
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                # 最后一个 chunk 包含 usage 信息
                if chunk.usage:
                    self.last_usage = {
                        "model": self._cloud_model,
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "cache_hit_tokens": getattr(chunk.usage, "prompt_cache_hit_tokens", 0) or 0,
                        "cache_miss_tokens": getattr(chunk.usage, "prompt_cache_miss_tokens", 0) or 0,
                    }
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
                # 提取用量信息
                if response.usage:
                    self.last_usage = {
                        "model": self._cloud_model,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "cache_hit_tokens": getattr(response.usage, "prompt_cache_hit_tokens", 0) or 0,
                        "cache_miss_tokens": getattr(response.usage, "prompt_cache_miss_tokens", 0) or 0,
                    }
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

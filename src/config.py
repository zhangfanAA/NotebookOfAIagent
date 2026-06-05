# 智能学习助手 — 全局配置管理
# 读取 settings.yaml，支持环境变量覆盖

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_config(config_path: str = None) -> dict:
    """
    加载配置文件，支持环境变量覆盖

    优先级: 环境变量 > settings.yaml > 默认值
    """
    path = Path(config_path) if config_path else CONFIG_PATH

    # 默认配置
    config = {
        "database": {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "1234",
            "database": "project",
            "pool_size": 5,
        },
        "llm": {
            "primary": {
                "provider": "ollama",
                "model": "qwen2.5:7b-instruct",
                "base_url": "http://localhost:11434",
                "timeout": 30,
            },
            "fallback": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "timeout": 30,
            },
        },
        "embedding": {
            "model": "BAAI/bge-m3",
            "device": "cpu",
        },
        "vector_store": {
            "persist_dir": str(PROJECT_ROOT / "data" / "chroma_db"),
            "collection_name": "course_materials",
        },
        "chunking": {
            "chunk_size": 500,
            "chunk_overlap": 50,
        },
        "agent": {
            "max_loops": 3,
            "retrieve_top_k": 5,
        },
        "app": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False,
        },
    }

    # 从 YAML 文件加载覆盖
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                _deep_merge(config, yaml_config)

    # 环境变量覆盖
    env_overrides = {
        "DB_HOST": ("database", "host"),
        "DB_PORT": ("database", "port"),
        "DB_USER": ("database", "user"),
        "DB_PASSWORD": ("database", "password"),
        "DB_NAME": ("database", "database"),
        "DEEPSEEK_API_KEY": ("llm", "fallback", "api_key"),
        "DEEPSEEK_BASE_URL": ("llm", "fallback", "base_url"),
        "OLLAMA_BASE_URL": ("llm", "primary", "base_url"),
        "OLLAMA_MODEL": ("llm", "primary", "model"),
        "APP_HOST": ("app", "host"),
        "APP_PORT": ("app", "port"),
    }

    for env_key, config_path_tuple in env_overrides.items():
        value = os.environ.get(env_key)
        if value is not None:
            _set_nested(config, config_path_tuple, value)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典，override 覆盖 base"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _set_nested(d: dict, keys: tuple, value):
    """设置嵌套字典的值"""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    # 尝试保持原始类型
    original = d.get(keys[-1])
    if original is not None:
        try:
            value = type(original)(value)
        except (ValueError, TypeError):
            pass
    d[keys[-1]] = value


# 全局配置单例
_config = None


def get_config() -> dict:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> dict:
    """重新加载配置"""
    global _config
    _config = load_config()
    return _config

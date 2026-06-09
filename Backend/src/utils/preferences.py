"""
智能学习助手 — 用户偏好持久化
负责: FULL
功能: 保存和加载用户偏好设置（深色模式、温度、Top-K 等）
"""

import json
from pathlib import Path
from src.logger import get_logger

logger = get_logger("utils.preferences")

# 偏好文件路径
PREFERENCES_PATH = Path(__file__).parent.parent.parent / "data" / "user_preferences.json"

# 默认偏好
DEFAULT_PREFERENCES = {
    "dark_mode": False,
    "temperature": 0.3,
    "top_k": 5,
    "max_loops": 3,
    "chunk_size": 500,
    "model_choice": "自动选择",
}


def load_preferences() -> dict:
    """
    加载用户偏好设置

    Returns:
        用户偏好字典，如果文件不存在则返回默认值
    """
    try:
        if PREFERENCES_PATH.exists():
            with open(PREFERENCES_PATH, "r", encoding="utf-8") as f:
                prefs = json.load(f)
                # 合并默认值（处理新增的偏好项）
                merged = {**DEFAULT_PREFERENCES, **prefs}
                logger.debug("加载用户偏好: %s", PREFERENCES_PATH)
                return merged
    except Exception as e:
        logger.warning("加载偏好失败: %s", str(e))

    return DEFAULT_PREFERENCES.copy()


def save_preferences(preferences: dict):
    """
    保存用户偏好设置

    Args:
        preferences: 偏好字典
    """
    try:
        PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PREFERENCES_PATH, "w", encoding="utf-8") as f:
            json.dump(preferences, f, ensure_ascii=False, indent=2)
        logger.debug("保存用户偏好: %s", PREFERENCES_PATH)
    except Exception as e:
        logger.warning("保存偏好失败: %s", str(e))


def update_preference(key: str, value):
    """
    更新单个偏好项

    Args:
        key: 偏好键名
        value: 偏好值
    """
    prefs = load_preferences()
    prefs[key] = value
    save_preferences(prefs)

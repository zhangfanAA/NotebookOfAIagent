"""
智能学习助手 — 通用工具函数
"""

import uuid
from datetime import datetime


def generate_id() -> str:
    """生成唯一 ID"""
    return str(uuid.uuid4())


def now_str() -> str:
    """当前时间 ISO 格式字符串"""
    return datetime.now().isoformat()


def truncate(text: str, max_length: int = 200) -> str:
    """截断文本，超过长度加省略号"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

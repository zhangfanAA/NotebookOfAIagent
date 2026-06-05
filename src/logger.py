# 智能学习助手 — 统一日志模块
# 所有模块通过 get_logger(name) 获取日志实例

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 已初始化的 logger 缓存
_initialized = False


def _setup_root_logger():
    """配置根日志记录器"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root_logger = logging.getLogger("learning_assistant")
    root_logger.setLevel(logging.DEBUG)

    # 控制台输出（INFO 级别以上）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # 文件输出（DEBUG 级别以上，自动轮转 5MB x 3）
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # 错误单独记录
    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志实例

    Args:
        name: 模块名称，如 "rag.retrieve", "data.pdf_parser"

    Returns:
        logging.Logger 实例

    Usage:
        from src.logger import get_logger
        logger = get_logger("rag.retrieve")
        logger.info("检索完成，返回 %d 个文档", len(docs))
    """
    _setup_root_logger()
    return logging.getLogger(f"learning_assistant.{name}")

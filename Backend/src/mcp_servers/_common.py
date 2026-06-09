"""
MCP 服务器共享模块

提供各 MCP Server 共用的工具函数:
- get_rag_service()  — RAGService 单例访问器
- get_user_llm()     — 用户级 LLMClient 工厂
- run_blocking()     — asyncio.to_thread 包装器
- to_json_string()   — JSON 序列化（处理 Decimal/datetime）
"""

import asyncio
import json
from decimal import Decimal
from datetime import datetime, date


# ===== RAGService 单例 =====

_rag_service = None


def get_rag_service():
    """获取 RAGService 单例（懒加载）"""
    global _rag_service
    if _rag_service is None:
        from src.rag.rag_service import RAGService
        _rag_service = RAGService()
    return _rag_service


# ===== 用户级 LLM 客户端 =====

def get_user_llm(user_id: int):
    """创建用户级 LLMClient（含 API Key、模型覆盖）"""
    from src.rag.llm_client import LLMClient
    return LLMClient.for_user(user_id)


# ===== 异步包装 =====

async def run_blocking(fn, *args, **kwargs):
    """将同步函数包装为异步调用（避免阻塞 MCP 事件循环）"""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ===== JSON 序列化 =====

def to_json_string(obj) -> str:
    """JSON 序列化，处理 Decimal/datetime 等非标准类型"""
    def _default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(obj, ensure_ascii=False, default=_default)

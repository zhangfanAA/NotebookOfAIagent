"""
Supervisor Agent — LangGraph ReAct Agent 调度 MCP 工具

核心组件:
- _build_llm()       — 根据用户配置构建 tool-calling LLM
- _build_mcp_config() — MCP Server 子进程配置
- _wrap_tools()       — 工具包装（自动注入 user_id/session_id）
- SupervisorGraph     — 可调用的 Agent 图

启动方式: 通过 FastAPI /api/agent/chat 或 /api/agent/stream 调用
"""

import sys

from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk
from langchain_core.tools import StructuredTool, BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState
from pydantic import create_model

from src.config import get_config, PROJECT_ROOT
from src.logger import get_logger
from src.supervisor.prompts import SUPERVISOR_PROMPT

logger = get_logger("supervisor.graph")


# ===== LLM 工厂 =====

def _build_llm(user_id: int):
    """
    根据数据库配置构建 ChatOpenAI（支持 tool calling）。

    复用 llm_client.py:89-129 的 provider 选择逻辑:
    - local   → Ollama OpenAI 兼容端点
    - cloud   → DeepSeek 等（含用户级 API Key）
    - balance → 管理员配置的共享模型
    """
    from langchain_openai import ChatOpenAI
    from src.database.global_config_repo import GlobalConfigRepository

    config = get_config()["llm"]
    repo = GlobalConfigRepository()
    cfg = repo.get(1)
    provider = cfg.get("llm_provider") or "local"

    if provider == "local":
        base_url = config["primary"]["base_url"].rstrip("/") + "/v1"
        model = config["primary"]["model"]
        return ChatOpenAI(
            base_url=base_url,
            api_key="ollama",
            model=model,
            temperature=0.1,
            streaming=True,
        )

    # cloud 或 balance 模式
    if provider == "balance":
        balance_cfg = repo.get(2)
        api_key = balance_cfg.get("api_key") or config["fallback"].get("api_key", "")
        base_url = (balance_cfg.get("base_url") or config["fallback"].get("base_url", "")).rstrip("/")
        model = balance_cfg.get("model") or config["fallback"].get("model", "")
    else:
        api_key = cfg.get("api_key") or config["fallback"].get("api_key", "")
        base_url = (cfg.get("base_url") or config["fallback"].get("base_url", "")).rstrip("/")
        model = cfg.get("model") or config["fallback"].get("model", "")

    # 检查用户级 API Key 覆盖
    if provider == "cloud":
        try:
            from src.database.user_repo import UserRepository
            user_settings = UserRepository().get_user_api_settings(user_id)
            if user_settings and user_settings.get("cloud_api_key"):
                api_key = user_settings["cloud_api_key"]
                base_url = (user_settings.get("cloud_base_url") or base_url).rstrip("/")
                model = user_settings.get("cloud_model") or model
        except Exception as e:
            logger.warning("读取用户 API Key 失败: %s", e)

    if not api_key:
        logger.warning("未配置 API Key，回退到 local 模式")
        base_url = config["primary"]["base_url"].rstrip("/") + "/v1"
        model = config["primary"]["model"]
        return ChatOpenAI(
            base_url=base_url,
            api_key="ollama",
            model=model,
            temperature=0.1,
            streaming=True,
        )

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.1,
        streaming=True,
    )


# ===== MCP 配置 =====

def _build_mcp_config() -> dict:
    """构建 MultiServerMCPClient 连接配置（stdio 子进程）"""
    project_root = str(PROJECT_ROOT)
    return {
        "rag": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "src.mcp_servers.rag_server"],
            "cwd": project_root,
        },
        "learning": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "src.mcp_servers.learning_tools_server"],
            "cwd": project_root,
        },
    }


# ===== 工具包装 =====

def _wrap_tools(
    tools: list[BaseTool],
    user_id: int,
    session_id: str | None,
) -> list[BaseTool]:
    """
    包装 MCP 工具，自动注入 user_id 和 session_id。

    - 从工具 schema 中移除 user_id（LLM 不可见，自动注入）
    - 对 rag_query 额外移除 session_id（从请求参数注入）
    - 安全性：LLM 无法越权访问其他用户数据
    """
    wrapped = []
    for tool in tools:
        wrapped.append(_wrap_single_tool(tool, user_id, session_id))
    return wrapped


def _wrap_single_tool(tool: BaseTool, user_id: int, session_id: str | None) -> BaseTool:
    """包装单个 MCP 工具"""
    original_schema = tool.args_schema or tool.get_input_schema()

    # 确定需要排除的字段
    excluded = {"user_id"}
    if tool.name == "rag_query" and session_id:
        excluded.add("session_id")

    # 构建新 schema（排除注入字段）
    fields = {}
    for name, field_info in original_schema.model_fields.items():
        if name not in excluded:
            fields[name] = (field_info.annotation, field_info)

    NewSchema = create_model(f"{tool.name}Input", **fields)

    async def wrapped_func(**kwargs):
        kwargs["user_id"] = user_id
        if tool.name == "rag_query" and session_id:
            kwargs["session_id"] = session_id
        return await tool.ainvoke(kwargs)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=NewSchema,
        coroutine=wrapped_func,
    )


# ===== Supervisor Agent 图 =====

class SupervisorGraph:
    """
    Supervisor Agent — 调度 MCP 工具的 LangGraph ReAct Agent

    Usage:
        async with SupervisorGraph(user_id=1, session_id="abc") as sg:
            result = await sg.ainvoke("我有哪些文档？")
            # 或流式:
            async for event in sg.astream("帮我总结文档"):
                print(event)
    """

    def __init__(self, user_id: int, session_id: str | None = None):
        self._user_id = user_id
        self._session_id = session_id
        self._llm = _build_llm(user_id)
        self._mcp_config = _build_mcp_config()
        self._graph = None
        self._tools = None

    async def __aenter__(self):
        """初始化：连接 MCP Server，加载并包装工具，构建 Agent 图"""
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient(self._mcp_config)
        raw_tools = await client.get_tools()
        logger.info("MCP 工具加载完成: %s", [t.name for t in raw_tools])

        self._tools = _wrap_tools(raw_tools, self._user_id, self._session_id)
        self._graph = self._build_graph()
        return self

    async def __aexit__(self, *args):
        """清理（MCP 子进程由 OS 回收）"""
        pass

    def _build_graph(self):
        """构建 ReAct Agent 图: agent ↔ tools"""
        llm_with_tools = self._llm.bind_tools(self._tools)

        async def agent_node(state: MessagesState):
            response = await llm_with_tools.ainvoke(state["messages"])
            return {"messages": [response]}

        tool_node = ToolNode(self._tools)

        def should_continue(state: MessagesState):
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                return "tools"
            return END

        graph = StateGraph(MessagesState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tool_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        compiled = graph.compile()
        logger.info("Supervisor Agent 图构建完成")
        return compiled

    async def ainvoke(self, question: str) -> dict:
        """非流式运行，返回最终答案"""
        system_msg = SystemMessage(content=SUPERVISOR_PROMPT)
        result = await self._graph.ainvoke({
            "messages": [system_msg, HumanMessage(content=question)]
        })
        final = result["messages"][-1]
        return {
            "answer": final.content,
            "tool_calls": _extract_tool_calls(result["messages"]),
        }

    async def astream(self, question: str):
        """流式运行，yield SSE 兼容的事件字典"""
        system_msg = SystemMessage(content=SUPERVISOR_PROMPT)
        input_msgs = {"messages": [system_msg, HumanMessage(content=question)]}

        async for event in self._graph.astream(input_msgs, stream_mode="updates"):
            for node_name, data in event.items():
                messages = data.get("messages", [])
                for msg in messages:
                    # LLM 决定调用工具
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            yield {
                                "type": "tool_call",
                                "tool": tc["name"],
                                "args": tc["args"],
                                "id": tc.get("id", ""),
                            }
                    # 工具返回结果
                    elif hasattr(msg, "name") and msg.name and hasattr(msg, "content"):
                        yield {
                            "type": "tool_result",
                            "tool": msg.name,
                            "content": _truncate(msg.content, 1000),
                        }
                    # LLM 生成的最终回答
                    elif isinstance(msg, AIMessageChunk) and msg.content:
                        yield {
                            "type": "token",
                            "content": msg.content,
                        }

        yield {"type": "done"}


# ===== 辅助函数 =====

def _extract_tool_calls(messages: list) -> list:
    """从消息历史中提取所有工具调用记录"""
    calls = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                calls.append({"tool": tc["name"], "args": tc["args"]})
    return calls


def _truncate(text: str, max_len: int = 1000) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."

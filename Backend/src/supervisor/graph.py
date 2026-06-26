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

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import StructuredTool, BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState

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
    """构建 MultiServerMCPClient 连接配置（SSE/HTTP 传输，避免 stdio 子进程问题）"""
    config = get_config()
    host = config.get("app", {}).get("host", "0.0.0.0")
    port = config.get("app", {}).get("port", 8000)
    base = f"http://127.0.0.1:{port}"
    return {
        "rag": {
            "transport": "sse",
            "url": f"{base}/mcp/rag/sse",
        },
        "learning": {
            "transport": "sse",
            "url": f"{base}/mcp/learning/sse",
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


def _build_filtered_schema(tool: BaseTool, excluded: set[str]):
    """从工具 schema 中移除内部字段（user_id / session_id），返回新的 Pydantic model"""
    from pydantic import create_model

    original = tool.args_schema or tool.get_input_schema()
    fields = {}

    if hasattr(original, "model_fields"):
        # Pydantic model
        for name, field_info in original.model_fields.items():
            if name not in excluded:
                fields[name] = (field_info.annotation, field_info)
    elif isinstance(original, dict):
        # JSON Schema dict
        properties = original.get("properties", {})
        required = set(original.get("required", []))
        for name, prop in properties.items():
            if name in excluded:
                continue
            t = prop.get("type", "string")
            py_type = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}.get(t, str)
            default = ... if name in required else None
            from pydantic import Field
            fields[name] = (py_type, Field(default=default, description=prop.get("description", "")))
    else:
        return None  # 无法解析，不包装

    return create_model(f"{tool.name}Input", **fields)


def _wrap_single_tool(tool: BaseTool, user_id: int, session_id: str | None) -> BaseTool:
    """包装单个 MCP 工具 — 从 schema 移除 user_id/session_id，调用时自动注入"""
    excluded = {"user_id"}
    if tool.name == "rag_query" and session_id:
        excluded.add("session_id")

    filtered_schema = _build_filtered_schema(tool, excluded)

    async def wrapped_call(input_data=None, **kwargs):
        import asyncio

        merged = dict(kwargs)
        if input_data is not None:
            if hasattr(input_data, "model_dump"):
                merged.update(input_data.model_dump())
            elif isinstance(input_data, dict):
                merged.update(input_data)

        merged["user_id"] = user_id
        if tool.name == "rag_query" and session_id:
            merged["session_id"] = session_id

        logger.debug("调用工具 %s: %s", tool.name, list(merged.keys()))
        try:
            result = await asyncio.wait_for(tool.ainvoke(merged), timeout=180)
            logger.debug("工具 %s 返回: %s", tool.name, str(result)[:200])
            return result
        except asyncio.TimeoutError:
            logger.error("工具 %s 调用超时 (180s)", tool.name)
            return f"工具 {tool.name} 调用超时（180秒）"
        except Exception as e:
            logger.error("工具 %s 失败: %s", tool.name, e)
            return f"工具调用失败: {e}"

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=filtered_schema or tool.args_schema,
        coroutine=wrapped_call,
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
        self._graph = None
        self._tools = None

    async def __aenter__(self):
        """初始化：加载工具，构建 Agent 图"""
        self._tools = self._build_direct_tools()
        logger.info("工具加载完成: %d 个工具", len(self._tools))
        self._graph = self._build_graph()
        return self

    def _build_direct_tools(self) -> list:
        """直接在主进程创建工具，避免 MCP 子进程开销"""
        from langchain_core.tools import StructuredTool
        from src.rag.rag_service import RAGService
        import asyncio, json

        rag = RAGService()
        uid = self._user_id
        sid = self._session_id

        async def _list_documents(**kwargs) -> str:
            docs = await asyncio.to_thread(rag.get_documents, user_id=uid)
            slim = [{k: v for k, v in d.items() if k != "full_text"} for d in docs]
            return json.dumps({"documents": slim}, ensure_ascii=False)

        async def _rag_query(question: str, **kwargs) -> str:
            from src.rag.llm_client import LLMClient
            user_llm = LLMClient.for_user(uid)
            result = await asyncio.to_thread(
                rag.query, question, sid or "", llm_client=user_llm, user_id=uid
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        async def _generate_quiz(file_names: list, count: int = 5, difficulty: str = "medium", **kwargs) -> str:
            from src.rag.llm_client import LLMClient
            user_llm = LLMClient.for_user(uid)
            result = await asyncio.to_thread(
                rag.generate_quiz, file_names, num_questions=count, difficulty=difficulty, llm_client=user_llm
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        async def _generate_mindmap(file_names: list, output_type: str = "mindmap", topic: str = "", **kwargs) -> str:
            from src.rag.llm_client import LLMClient
            user_llm = LLMClient.for_user(uid)
            result = await asyncio.to_thread(
                rag.generate_content, file_names, user_prompt=topic, output_type=output_type, llm_client=user_llm
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        async def _generate_flashcards(file_names: list, topic: str = "", count: int = 10, **kwargs) -> str:
            from src.rag.llm_client import LLMClient
            user_llm = LLMClient.for_user(uid)
            result = await asyncio.to_thread(
                rag.generate_flashcards, file_names, num_cards=count, topic_focus=topic, llm_client=user_llm
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        async def _compare_documents(file_names: list, focus: str = "", **kwargs) -> str:
            from src.rag.llm_client import LLMClient
            user_llm = LLMClient.for_user(uid)
            result = await asyncio.to_thread(
                rag.compare_documents, file_names, focus=focus, llm_client=user_llm
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        def _make_tool(func, name, desc):
            # 提取非 **kwargs 参数作为 schema
            import inspect
            sig = inspect.signature(func)
            params = [(n, p) for n, p in sig.parameters.items() if n != "kwargs"]

            # 创建 Pydantic schema
            from pydantic import create_model, Field
            fields = {}
            for pname, p in params:
                annotation = p.annotation if p.annotation != inspect.Parameter.empty else str
                default = p.default if p.default != inspect.Parameter.empty else ...
                fields[pname] = (annotation, Field(default=default, description=""))

            schema = create_model(f"{name}Args", **fields) if fields else None

            return StructuredTool(
                name=name,
                description=desc,
                coroutine=func,
                args_schema=schema,
            )

        return [
            _make_tool(_rag_query, "rag_query", "基于已上传文档进行智能问答。参数: question (问题文本)"),
            _make_tool(_list_documents, "list_documents", "列出用户的已上传文档。无需参数"),
            _make_tool(_generate_quiz, "generate_quiz", "基于文档生成测验题。参数: file_names (文件名列表), count (题目数量, 默认5), difficulty (难度, 默认中等)"),
            _make_tool(_generate_mindmap, "generate_mindmap", "基于文档生成思维导图或重点笔记。参数: file_names (文件名列表), output_type (mindmap或notes), topic (主题)"),
            _make_tool(_generate_flashcards, "generate_flashcards", "基于文档生成闪卡。参数: file_names (文件名列表), topic (主题), count (数量)"),
            _make_tool(_compare_documents, "compare_documents", "对比文档异同。参数: file_names (文件名列表), focus (对比焦点)"),
        ]

    async def __aexit__(self, *args):
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
        """流式运行，yield SSE 兼容的事件字典，支持 token 级流式输出"""
        import asyncio

        system_msg = SystemMessage(content=SUPERVISOR_PROMPT)
        input_msgs = {"messages": [system_msg, HumanMessage(content=question)]}

        logger.info("Agent astream 开始，问题: %s", question[:100])

        try:
            # 使用 updates 模式获取完整节点输出（工具调用/结果 + 最终回答）
            async for event in self._graph.astream(input_msgs, stream_mode="updates"):
                try:
                    for node_name, data in event.items():
                        messages = data.get("messages", [])
                        for msg in messages:
                            # 工具调用
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    logger.info("Agent 工具调用: %s(%s)", tc["name"], tc.get("args", {}))
                                    yield {
                                        "type": "tool_call",
                                        "tool": tc["name"],
                                        "args": tc["args"],
                                        "id": tc.get("id", ""),
                                    }
                            # 工具结果
                            if hasattr(msg, "name") and msg.name and hasattr(msg, "content"):
                                if isinstance(msg.content, list):
                                    text_parts = [c.get("text", "") for c in msg.content if isinstance(c, dict)]
                                    content_str = "\n".join(text_parts)
                                else:
                                    content_str = str(msg.content)
                                truncate_len = 50000 if msg.name == "rag_query" else 5000
                                logger.info("Agent 工具结果: %s -> %s", msg.name, content_str[:200])
                                yield {
                                    "type": "tool_result",
                                    "tool": msg.name,
                                    "content": _truncate(content_str, truncate_len),
                                }
                            # LLM 最终回答（完整消息，非工具调用）
                            if node_name == "agent" and hasattr(msg, "content") and msg.content:
                                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                    if not (hasattr(msg, "name") and msg.name):
                                        logger.info("Agent 最终回答: %s", str(msg.content)[:100])
                                        yield {
                                            "type": "token",
                                            "content": msg.content,
                                        }
                except Exception as e:
                    logger.warning("Agent 事件处理异常: %s", e)
                    continue

        except Exception as e:
            logger.error("Agent astream 异常: %s", e, exc_info=True)
            yield {"type": "token", "content": f"⚠️ Agent 执行出错: {str(e)[:200]}"}

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


def _truncate(text: str, max_len: int = 5000) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."

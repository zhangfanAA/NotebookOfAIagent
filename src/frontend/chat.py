"""
智能学习助手 — 主聊天区域渲染
负责: FULL

包含: 消息展示、流式输出、诊断提示
"""

import streamlit as st

from src.frontend.components import (
    get_friendly_error,
    render_latex_content,
    render_sources,
    render_error_toast,
)


def render_main_area(rag):
    """渲染主聊天区域"""
    if "session_id" not in st.session_state:
        session_id = rag.create_session()
        st.session_state["session_id"] = session_id
        st.session_state["messages"] = []

    if "messages" not in st.session_state:
        sid = st.session_state.get("session_id")
        st.session_state["messages"] = rag.get_session_history(sid) if sid else []

    if not st.session_state["messages"]:
        _render_welcome()

    _render_messages(rag)
    _handle_input(rag)


def _render_welcome():
    """渲染欢迎信息"""
    with st.chat_message("assistant"):
        st.markdown("""## 👋 你好！我是智能学习助手

我可以帮你理解课件内容、解答学习问题。

### 🚀 快速开始

1. **上传课件** — 在左侧面板上传 PDF 文件
2. **提出问题** — 在下方输入框输入你的问题
3. **获取答案** — 我会从课件中检索相关内容并给出解答

### ✨ 主要功能

- 📚 **知识库问答** — 基于上传的课件回答问题
- 🔍 **智能检索** — 语义搜索，找到最相关的内容
- 📊 **学习诊断** — 分析你的学习薄弱点
- 📝 **会话笔记** — 为每个会话添加学习笔记
- ⭐ **答案收藏** — 收藏有价值的回答
- 📤 **对话导出** — 导出为 Markdown 或 HTML 格式

### 💡 示例问题
""")
        suggestions = [
            "什么是存储系统？",
            "解释虚拟内存的概念",
            "什么是中断处理？",
            "CPU调度算法有哪些？",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(s, key=f"suggest_{i}", use_container_width=True):
                    st.session_state["_pending_input"] = s
                    st.rerun()


def _render_messages(rag):
    """渲染历史消息"""
    messages = st.session_state["messages"]
    # 如果刚完成流式输出，跳过最后一条助手消息（已由 _handle_input 渲染）
    skip_last = st.session_state.pop("_streamed_last", False)
    render_count = len(messages) - 1 if (skip_last and messages and messages[-1].get("role") == "assistant") else len(messages)
    for i in range(render_count):
        msg = messages[i]
        role = msg.get("role", "user")
        content = msg.get("content", "")
        sources = msg.get("sources")
        confidence = msg.get("confidence")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                render_latex_content(content)
                if sources:
                    render_sources(sources, confidence)
                _render_message_actions(rag, i, msg, content)


def _render_message_actions(rag, i, msg, content):
    """渲染消息操作按钮"""
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 3])
    with col1:
        st.button("📋", key=f"copy_{i}", on_click=lambda c=content: st.session_state.update({"_copied": c}))
    with col2:
        if st.button("⭐", key=f"fav_{i}"):
            sid = st.session_state.get("session_id")
            if sid:
                user_msgs_before = [m for q_idx, m in enumerate(st.session_state["messages"][:i]) if m.get("role") == "user"]
                question = user_msgs_before[-1]["content"] if user_msgs_before else None
                rag.add_favorite(sid, content, question)
                st.toast("已收藏！")
    with col3:
        if st.button("👍", key=f"good_{i}"):
            st.toast("感谢反馈！")
    with col4:
        if st.button("👎", key=f"bad_{i}"):
            st.toast("已记录")
    if i == len(st.session_state["messages"]) - 1:
        with col5:
            if st.button("🔄 重新生成", key="regen"):
                user_msgs = [m for m in st.session_state["messages"] if m.get("role") == "user"]
                if user_msgs:
                    st.session_state["messages"].pop()
                    st.session_state["_pending_input"] = user_msgs[-1]["content"]
                    st.rerun()


def _handle_input(rag):
    """处理用户输入"""
    pending = st.session_state.pop("_pending_input", None)
    prompt = pending or st.chat_input("输入你的问题...")
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            full_answer = ""
            sources = []
            confidence = None
            diagnosis = {}
            error_msg = None
            context_info = None
            message_placeholder = st.empty()
            status_placeholder = st.empty()
            with status_placeholder.container():
                st.caption("🔍 正在检索知识库...")
            for chunk in rag.query_stream(prompt, st.session_state["session_id"]):
                if chunk["type"] == "token":
                    status_placeholder.empty()
                    full_answer += chunk["data"]
                    message_placeholder.markdown(full_answer + "▌")
                elif chunk["type"] == "result":
                    rd = chunk["data"]
                    sources = rd.get("sources", [])
                    confidence = rd.get("confidence")
                    diagnosis = rd.get("diagnosis", {})
                    if rd.get("context_used"):
                        context_info = {
                            "original": rd.get("original_question", ""),
                            "rewritten": rd.get("rewritten_question", ""),
                        }
                elif chunk["type"] == "error":
                    error_msg = chunk["data"]
            render_latex_content(full_answer)
            status_placeholder.empty()
            if error_msg:
                friendly_msg = get_friendly_error(error_msg)
                render_error_toast(friendly_msg, error_msg)
            else:
                if context_info:
                    with st.expander("🔗 上下文增强", expanded=False):
                        st.caption(f"原始问题: {context_info['original']}")
                        st.caption(f"理解为: {context_info['rewritten']}")
                if diagnosis.get("triggered"):
                    st.warning(f"📊 学习诊断: 你已经就「{diagnosis['topic']}」提问了 {diagnosis['count']} 次。{diagnosis.get('suggestion', '')}")
                render_sources(sources, confidence)
                st.session_state["messages"].append({"role": "assistant", "content": full_answer, "sources": sources, "confidence": confidence})
                st.session_state["_streamed_last"] = True
        if diagnosis.get("triggered"):
            st.rerun()

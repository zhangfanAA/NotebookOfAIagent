"""
智能学习助手 — 侧边栏渲染
负责: FULL

包含: 会话列表、上传、知识库管理、诊断、统计
"""

import os
import streamlit as st

from src.frontend.export import generate_export_md, generate_export_html
from src.frontend.components import render_health_check


def render_sidebar(rag):
    """渲染完整侧边栏"""
    with st.sidebar:
        st.title("📚 智能学习助手")
        col1, col2 = st.columns([3, 1])
        with col2:
            dark = st.toggle("🌙", value=st.session_state.get("dark_mode", False), key="dark_toggle")
            st.session_state["dark_mode"] = dark

        _render_settings()
        st.divider()

        _render_new_session(rag)
        _render_export_buttons(rag)
        st.divider()

        _render_session_list(rag)
        _render_clear_all(rag)

        session_id = st.session_state.get("session_id")
        if session_id:
            _render_favorites(rag, session_id)
            _render_diagnostics(rag, session_id)
            _render_progress(rag, session_id)

        _render_session_stats()
        st.divider()

        _render_upload(rag)
        st.divider()

        _render_knowledge_base(rag)
        st.divider()
        render_health_check()


def _render_settings():
    """渲染设置面板"""
    with st.expander("⚙️ 设置", expanded=False):
        model_choice = st.selectbox("大模型", ["Ollama (本地)", "DeepSeek (云端)", "自动"], index=2, key="model_choice")
        temperature = st.slider("温度", 0.0, 1.0, 0.3, 0.1, key="temperature")
        if temperature > 0.7:
            st.warning("温度过高可能降低回答准确性")
        top_k = st.slider("检索数量", 1, 10, 5, 1, key="top_k")
        max_loops = st.slider("最大重试", 1, 5, 3, 1, key="max_loops")
        chunk_size = st.slider("分块大小", 200, 1000, 500, 50, key="chunk_size")


def _render_new_session(rag):
    """渲染新建会话按钮"""
    if st.button("➕ 新建会话", use_container_width=True):
        session_id = rag.create_session()
        st.session_state["session_id"] = session_id
        st.session_state["messages"] = []
        st.rerun()


def _render_export_buttons(rag):
    """渲染导出按钮"""
    messages = st.session_state.get("messages", [])
    if messages:
        export_md = generate_export_md(messages)
        export_html = generate_export_html(messages)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 MD", data=export_md, file_name="对话记录.md", mime="text/markdown", use_container_width=True)
        with col2:
            st.download_button("📥 HTML", data=export_html, file_name="对话记录.html", mime="text/html", use_container_width=True)


def _render_session_list(rag):
    """渲染会话列表"""
    st.subheader("💬 会话历史")
    search_query = st.text_input("🔍", "", key="session_search", placeholder="搜索会话（标题或内容）...")
    try:
        if search_query:
            sessions = rag.search_sessions(search_query)
        else:
            sessions = rag.get_sessions()
        if sessions:
            for s in sessions:
                sid = s["session_id"]
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    btn_label = s.get("title", "新会话")[:25]
                    if st.button(btn_label, key=f"session_{sid}", use_container_width=True):
                        st.session_state["session_id"] = sid
                        st.session_state["messages"] = rag.get_session_history(sid)
                        st.rerun()
                with col2:
                    if st.button("📝", key=f"notes_{sid}"):
                        st.session_state[f"show_notes_{sid}"] = not st.session_state.get(f"show_notes_{sid}", False)
                        st.rerun()
                with col3:
                    if st.button("✏️", key=f"rename_{sid}"):
                        st.session_state[f"editing_{sid}"] = True
                        st.rerun()
                with col4:
                    if st.button("🗑️", key=f"del_{sid}"):
                        rag.delete_session(sid)
                        if st.session_state.get("session_id") == sid:
                            st.session_state.pop("session_id", None)
                            st.session_state["messages"] = []
                        st.rerun()
                if st.session_state.get(f"editing_{sid}"):
                    new_title = st.text_input("新标题", value=s.get("title", ""), key=f"new_title_{sid}", max_chars=30)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("保存", key=f"save_{sid}"):
                            if new_title.strip():
                                rag.update_session_title(sid, new_title.strip())
                                st.session_state.pop(f"editing_{sid}", None)
                                st.rerun()
                    with c2:
                        if st.button("取消", key=f"cancel_{sid}"):
                            st.session_state.pop(f"editing_{sid}", None)
                            st.rerun()
                if st.session_state.get(f"show_notes_{sid}"):
                    current_notes = rag.get_session_notes(sid)
                    new_notes = st.text_area("学习笔记", value=current_notes, key=f"notes_text_{sid}", height=100)
                    if st.button("保存笔记", key=f"save_notes_{sid}"):
                        rag.update_session_notes(sid, new_notes)
                        st.success("笔记已保存")
                        st.rerun()
        else:
            st.caption("未找到会话" if search_query else "暂无会话")
    except Exception as e:
        st.warning(f"加载会话失败: {e}")


def _render_clear_all(rag):
    """渲染清空所有会话按钮"""
    if st.button("🗑️ 清空所有会话", key="clear_all", use_container_width=True):
        try:
            for s in rag.get_sessions():
                rag.delete_session(s["session_id"])
            st.session_state.pop("session_id", None)
            st.session_state["messages"] = []
            st.success("已清空所有会话")
            st.rerun()
        except Exception as e:
            st.error(f"操作失败: {e}")


def _render_favorites(rag, session_id):
    """渲染收藏夹"""
    with st.expander("⭐ 收藏夹", expanded=False):
        try:
            favorites = rag.get_favorites(session_id)
            if favorites:
                for fav in favorites:
                    fav_id = fav.get("id")
                    content_preview = fav.get("content", "")[:80]
                    question = fav.get("question", "")
                    if question:
                        st.caption(f"Q: {question[:30]}...")
                    st.caption(f"A: {content_preview}...")
                    if st.button("🗑️ 取消收藏", key=f"unfav_{fav_id}"):
                        rag.remove_favorite(fav_id)
                        st.rerun()
                    st.divider()
            else:
                st.caption("暂无收藏")
        except Exception:
            st.caption("加载中...")


def _render_diagnostics(rag, session_id):
    """渲染学习诊断"""
    try:
        weak_topics = rag.get_weak_topics(session_id)
        if weak_topics:
            with st.expander("📊 学习诊断", expanded=False):
                for t in weak_topics:
                    st.caption(f"  {t.get('topic', '')} ({t.get('question_count', 0)}次)")
    except Exception:
        pass


def _render_progress(rag, session_id):
    """渲染学习进度"""
    if len(st.session_state.get("messages", [])) >= 2:
        with st.expander("📈 学习进度", expanded=False):
            try:
                progress = rag.get_learning_progress(session_id)
                st.metric("提问次数", progress.get("total_questions", 0))
                st.metric("平均置信度", f"{progress.get('avg_confidence', 0):.0%}")
                gaps = progress.get("knowledge_gaps", [])
                if gaps:
                    st.caption("知识缺口:")
                    for gap in gaps:
                        st.caption(f"  - {gap['topic']} ({gap['question_count']}次)")
            except Exception:
                st.caption("加载中...")


def _render_session_stats():
    """渲染会话统计"""
    current_msgs = st.session_state.get("messages", [])
    if current_msgs:
        user_count = sum(1 for m in current_msgs if m.get("role") == "user")
        assistant_msgs = [m for m in current_msgs if m.get("role") == "assistant"]
        confidences = [m.get("confidence", 0) for m in assistant_msgs if m.get("confidence") is not None]
        with st.expander("📋 会话统计", expanded=False):
            st.caption(f"消息: {user_count} 条提问 / {len(assistant_msgs)} 条回答")
            if confidences:
                avg = sum(confidences) / len(confidences)
                st.caption(f"平均置信度: {avg:.0%}")


def _render_upload(rag):
    """渲染上传区域"""
    st.subheader("📤 上传课件")
    uploaded_files = st.file_uploader("选择 PDF 文件（支持多选）", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        if st.button("📥 导入知识库", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            total = len(uploaded_files)
            for idx, f in enumerate(uploaded_files):
                status_text.caption(f"处理中 ({idx + 1}/{total}): {f.name}")
                progress_bar.progress(idx / total)
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "pdfs")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f.name)
                with open(temp_path, "wb") as fh:
                    fh.write(f.read())
                result = rag.upload_document(temp_path)
                if result["status"] == "success":
                    st.success(f"{f.name}: {result['message']}")
                else:
                    st.error(f"{f.name}: {result['message']}")
            progress_bar.progress(1.0)
            st.rerun()


def _render_knowledge_base(rag):
    """渲染知识库区域"""
    st.subheader("🗄️ 知识库")
    try:
        stats = rag.get_vector_db_stats()
        if "error" not in stats:
            st.metric("文档数", stats.get("total_documents", 0))
            st.metric("知识片段", stats.get("total_chunks", 0))
    except Exception:
        st.caption("知识库未初始化")

    with st.expander("📂 文档管理", expanded=False):
        try:
            docs = rag.get_documents()
            if docs:
                for doc in docs:
                    doc_id = doc.get("id")
                    name = doc.get("file_name", "?")
                    status = doc.get("status", "unknown")
                    chunks = doc.get("chunks_count", 0)
                    size_kb = doc.get("file_size", 0) / 1024
                    uploaded = doc.get("uploaded_at", "")[:16]
                    icon = "✅" if status == "ready" else ("⏳" if status == "processing" else "❌")
                    with st.expander(f"{icon} {name}", expanded=False):
                        st.caption(f"大小: {size_kb:.0f}KB | 分块: {chunks} | 上传: {uploaded}")
                        if status == "error":
                            st.error(f"错误: {doc.get('error_message', '未知错误')}")
                        if st.button("🗑️ 删除文档", key=f"del_doc_{doc_id}"):
                            rag.delete_document(doc_id)
                            st.rerun()
            else:
                st.caption("暂无文档，请上传 PDF 课件")
        except Exception as e:
            st.caption(f"加载失败: {e}")

    with st.expander("📊 知识库统计", expanded=False):
        try:
            docs = rag.get_documents()
            if docs:
                status_counts = {}
                for doc in docs:
                    s = doc.get("status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1
                status_labels = {"ready": "就绪", "processing": "处理中", "error": "错误"}
                chart_data = {status_labels.get(k, k): v for k, v in status_counts.items()}
                st.bar_chart(chart_data)

                ready_docs = [d for d in docs if d.get("status") == "ready" and d.get("chunks_count", 0) > 0]
                if ready_docs:
                    chunks_data = {d.get("file_name", "?")[:15]: d.get("chunks_count", 0) for d in ready_docs}
                    st.caption("各文档分块数:")
                    st.bar_chart(chunks_data)
            else:
                st.caption("暂无统计数据")
        except Exception:
            st.caption("加载中...")

    with st.expander("🔍 搜索知识库", expanded=False):
        kb_search = st.text_input("搜索", "", key="kb_search", placeholder="输入关键词...")
        if kb_search:
            try:
                from src.data.vector_store import search
                results = search(kb_search, top_k=3)
                if results:
                    for r in results:
                        src = r.get("metadata", {}).get("source", "?")
                        pg = r.get("metadata", {}).get("page", "?")
                        sc = r.get("score", 0)
                        st.caption(f"{src} 第{pg}页 ({sc:.0%})")
                else:
                    st.caption("未找到相关内容")
            except Exception as e:
                st.caption(f"搜索失败: {e}")

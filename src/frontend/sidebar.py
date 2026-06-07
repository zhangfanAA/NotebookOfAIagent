"""
智能学习助手 — 侧边栏渲染
负责: FULL

包含: 会话列表、上传、知识库管理、诊断、统计
"""

import os
import streamlit as st

from src.frontend.export import generate_export_md, generate_export_html
from src.frontend.components import render_health_check


_PANEL_KEYS = ["show_mindmap", "show_quiz", "show_flashcard", "show_stats", "show_compare"]


def _toggle_panel(key: str):
    """切换面板：点击的面板取反，其他全部关闭"""
    current = st.session_state.get(key, False)
    for k in _PANEL_KEYS:
        st.session_state[k] = False
    st.session_state[key] = not current


def render_sidebar(rag):
    """渲染完整侧边栏"""
    with st.sidebar:
        st.title("📚 智能学习助手")
        col1, col2 = st.columns([3, 1])
        with col2:
            dark = st.toggle("🌙", value=st.session_state.get("dark_mode", False), key="dark_toggle")
            st.session_state["dark_mode"] = dark

        # 面板快捷按钮
        row1 = st.columns(4)
        with row1[0]:
            is_open = st.session_state.get("show_mindmap", False)
            mm_label = "✕ 导图" if is_open else "🗺️ 导图"
            if st.button(mm_label, key="toggle_mindmap_btn", use_container_width=True):
                _toggle_panel("show_mindmap")
                st.rerun()
        with row1[1]:
            is_quiz = st.session_state.get("show_quiz", False)
            qz_label = "✕ 测验" if is_quiz else "📝 测验"
            if st.button(qz_label, key="toggle_quiz_btn", use_container_width=True):
                _toggle_panel("show_quiz")
                st.rerun()
        with row1[2]:
            is_fc = st.session_state.get("show_flashcard", False)
            fc_label = "✕ 闪卡" if is_fc else "🃏 闪卡"
            if st.button(fc_label, key="toggle_fc_btn", use_container_width=True):
                _toggle_panel("show_flashcard")
                st.rerun()
        with row1[3]:
            is_stats = st.session_state.get("show_stats", False)
            st_label = "✕ 统计" if is_stats else "📊 统计"
            if st.button(st_label, key="toggle_stats_btn", use_container_width=True):
                _toggle_panel("show_stats")
                st.rerun()

        row2 = st.columns(4)
        with row2[0]:
            is_cmp = st.session_state.get("show_compare", False)
            cmp_label = "✕ 对比" if is_cmp else "🔍 对比"
            if st.button(cmp_label, key="toggle_compare_btn", use_container_width=True):
                _toggle_panel("show_compare")
                st.rerun()

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
        _render_reading_progress(rag)
        _render_bookmarks(rag)
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

    # 批量操作模式
    batch_mode = st.toggle("批量操作", key="batch_mode_toggle")

    try:
        if search_query:
            sessions = rag.search_sessions(search_query)
        else:
            sessions = rag.get_sessions()
        if sessions:
            # 批量操作按钮
            if batch_mode:
                selected_sids = []
                for s in sessions:
                    sid = s["session_id"]
                    if st.checkbox(s.get("title", "新会话")[:25], key=f"batch_{sid}"):
                        selected_sids.append(sid)
                if selected_sids:
                    st.caption(f"已选 {len(selected_sids)} 个会话")
                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        if st.button("🗑️ 批量删除", key="batch_delete", use_container_width=True):
                            for sid in selected_sids:
                                rag.delete_session(sid)
                                if st.session_state.get("session_id") == sid:
                                    st.session_state.pop("session_id", None)
                                    st.session_state["messages"] = []
                            st.success(f"已删除 {len(selected_sids)} 个会话")
                            st.rerun()
                    with bcol2:
                        if st.button("📥 批量导出", key="batch_export", use_container_width=True):
                            all_msgs = []
                            for sid in selected_sids:
                                msgs = rag.get_session_history(sid)
                                all_msgs.extend(msgs)
                            if all_msgs:
                                md = generate_export_md(all_msgs)
                                st.download_button("下载合并记录", data=md, file_name="批量导出.md", mime="text/markdown")
                st.divider()

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


def _render_reading_progress(rag):
    """渲染阅读进度"""
    with st.expander("📖 阅读进度", expanded=False):
        try:
            progress_list = rag.get_all_reading_progress()
            if progress_list:
                for p in progress_list:
                    name = p.get("file_name", "?")
                    current = p.get("current_page", 0)
                    total = p.get("total_pages", 0)
                    is_done = p.get("is_finished", 0)
                    icon = "✅" if is_done else "📄"
                    if total > 0:
                        pct = current / total
                        st.caption(f"{icon} {name}")
                        st.progress(pct)
                        st.caption(f"  第 {current}/{total} 页 ({pct:.0%})")
                    else:
                        st.caption(f"{icon} {name} — 第 {current} 页")
            else:
                st.caption("暂无阅读记录")
        except Exception:
            st.caption("加载中...")


def _render_bookmarks(rag):
    """渲染书签列表"""
    with st.expander("🔖 书签", expanded=False):
        try:
            bookmarks = rag.get_all_bookmarks()
            if bookmarks:
                for bm in bookmarks:
                    fname = bm.get("file_name", "?")
                    page = bm.get("page_number", 0)
                    title = bm.get("title", "")
                    note = bm.get("note", "")
                    label = f"{fname} 第{page}页"
                    if title:
                        label += f" — {title}"
                    st.caption(label)
                    if note:
                        st.caption(f"  备注: {note}")
            else:
                st.caption("暂无书签")
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
    with st.expander("📊 知识库概览", expanded=False):
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

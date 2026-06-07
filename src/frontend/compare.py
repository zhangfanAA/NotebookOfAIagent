"""
智能学习助手 — 文档对比面板
负责: FULL

选中 2 个文件 → LLM 生成差异分析。
"""

import streamlit as st


def render_compare_panel(rag):
    """渲染文档对比面板"""
    with st.container():
        st.markdown("### 🔍 文档对比")

        available_docs = _get_available_docs(rag)
        if len(available_docs) < 2:
            st.info("📭 至少需要上传 2 个 PDF 课件")
            return

        seen = set()
        unique_docs = []
        for doc in available_docs:
            if doc["file_name"] not in seen:
                seen.add(doc["file_name"])
                unique_docs.append(doc)

        selected = []
        for doc in unique_docs:
            if st.checkbox(
                doc["file_name"],
                key=f"cmp_chk_{doc['file_name']}",
            ):
                selected.append(doc["file_name"])

        focus = st.text_input(
            "对比聚焦点",
            "",
            placeholder="例如：两者在算法复杂度上的差异",
            key="cmp_focus",
        )

        if st.button("🔍 开始对比", use_container_width=True, type="primary",
                      disabled=len(selected) < 2, key="btn_compare"):
            _do_compare(rag, selected, focus)

        st.divider()
        _render_result()


def _get_available_docs(rag):
    try:
        docs = rag.get_documents()
        return [
            {"file_name": d["file_name"], "id": d["id"], "chunks": d.get("chunks_count", 0)}
            for d in docs
            if d.get("status") == "ready"
        ]
    except Exception:
        return []


def _do_compare(rag, file_names, focus):
    with st.spinner("正在对比分析..."):
        result = rag.compare_documents(file_names, focus)

    if result["status"] == "success":
        st.session_state["_compare_result"] = result["content"]
        st.success(result["message"])
    else:
        st.error(result["message"])


def _render_result():
    content = st.session_state.get("_compare_result")
    if not content:
        st.caption("选择两个文件后点击对比")
        return

    st.markdown(content)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 下载", data=content, file_name="文档对比.md", mime="text/markdown", use_container_width=True)
    with col2:
        if st.button("🗑️ 清除", use_container_width=True):
            st.session_state.pop("_compare_result", None)
            st.rerun()

"""
智能学习助手 — 闪卡面板
负责: FULL

右侧可收起的闪卡生成面板。
选中文件 → 生成闪卡 → 翻转交互 → 标记掌握/未掌握。
"""

import streamlit as st


def render_flashcard_panel(rag):
    """渲染闪卡面板"""
    with st.container():
        st.markdown("### 🃏 闪卡复习")

        # 文件选择
        available_docs = _get_available_docs(rag)
        if not available_docs:
            st.info("📭 请先上传 PDF 课件")
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
                key=f"fc_chk_{doc['file_name']}",
                help=f"{doc.get('chunks', 0)} 个知识片段",
            ):
                selected.append(doc["file_name"])

        col1, col2 = st.columns(2)
        with col1:
            num_cards = st.slider("数量", 5, 30, 10, key="fc_num")
        with col2:
            topic_focus = st.text_input("聚焦主题", "", key="fc_topic", placeholder="可选")

        if st.button("🃏 生成闪卡", use_container_width=True, type="primary", disabled=not selected, key="btn_gen_fc"):
            _do_generate(rag, selected, num_cards, topic_focus)

        st.divider()
        _render_cards(rag)


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


def _do_generate(rag, file_names, num_cards, topic_focus):
    with st.spinner("正在生成闪卡..."):
        result = rag.generate_flashcards(file_names, num_cards, topic_focus)

    if result["status"] == "success":
        st.session_state["_fc_cards"] = result["cards"]
        st.session_state["_fc_index"] = 0
        st.session_state["_fc_flipped"] = False
        st.session_state["_fc_mastered"] = {}
        st.success(result["message"])
    else:
        st.error(result["message"])


def _render_cards(rag):
    cards = st.session_state.get("_fc_cards")
    if not cards:
        st.caption("选择文件后点击生成闪卡")
        return

    index = st.session_state.get("_fc_index", 0)
    flipped = st.session_state.get("_fc_flipped", False)
    mastered = st.session_state.get("_fc_mastered", {})

    if index >= len(cards):
        # 全部复习完
        total = len(cards)
        mastered_count = sum(1 for v in mastered.values() if v)
        st.success(f"🎉 全部 {total} 张闪卡复习完毕！")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总数", total)
        with col2:
            st.metric("已掌握", mastered_count)
        with col3:
            st.metric("未掌握", total - mastered_count)
        if st.button("🔄 重新开始", use_container_width=True):
            st.session_state["_fc_index"] = 0
            st.session_state["_fc_flipped"] = False
            st.session_state["_fc_mastered"] = {}
            st.rerun()
        return

    card = cards[index]
    category = card.get("category", "")

    # 进度条
    st.progress((index) / len(cards))
    st.caption(f"第 {index + 1} / {len(cards)} 张" + (f"  ·  {category}" if category else ""))

    # 闪卡渲染
    card_style = """
    <div style="background: linear-gradient(135deg, #e8f4fd, #dbeafe); border: 1px solid #93c5fd;
                border-radius: 16px; padding: 24px; min-height: 150px; display: flex;
                align-items: center; justify-content: center; text-align: center;
                font-size: 1.1em; line-height: 1.6; margin: 12px 0;">
        {content}
    </div>
    """

    if not flipped:
        st.markdown(card_style.format(content=f"**问题：**<br><br>{card.get('front', '')}"), unsafe_allow_html=True)
    else:
        st.markdown(card_style.format(content=f"**答案：**<br><br>{card.get('back', '')}"), unsafe_allow_html=True)

    # 操作按钮
    if not flipped:
        if st.button("🔄 翻转查看答案", use_container_width=True, type="primary"):
            st.session_state["_fc_flipped"] = True
            st.rerun()
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ 已掌握", use_container_width=True, type="primary"):
                mastered[index] = True
                st.session_state["_fc_mastered"] = mastered
                st.session_state["_fc_index"] = index + 1
                st.session_state["_fc_flipped"] = False
                st.rerun()
        with col2:
            if st.button("❌ 未掌握", use_container_width=True):
                mastered[index] = False
                st.session_state["_fc_mastered"] = mastered
                st.session_state["_fc_index"] = index + 1
                st.session_state["_fc_flipped"] = False
                st.rerun()
        with col3:
            if st.button("↩️ 再看一次", use_container_width=True):
                st.session_state["_fc_flipped"] = False
                st.rerun()

    # 底部操作
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清除闪卡", use_container_width=True):
            for k in ["_fc_cards", "_fc_index", "_fc_flipped", "_fc_mastered"]:
                st.session_state.pop(k, None)
            st.rerun()

"""
智能学习助手 — 测验面板
负责: FULL

右侧可收起的测验生成面板。
选中文件 → 生成题目 → 答题交互 → 自动判分。
"""

import streamlit as st


def render_quiz_panel(rag):
    """渲染测验面板"""
    with st.container():
        st.markdown("### 📝 智能测验")

        # 文件选择
        available_docs = _get_available_docs(rag)
        if not available_docs:
            st.info("📭 请先上传 PDF 课件")
            return

        # 去重
        seen = set()
        unique_docs = []
        for doc in available_docs:
            if doc["file_name"] not in seen:
                seen.add(doc["file_name"])
                unique_docs.append(doc)

        # 文件多选
        selected = []
        for doc in unique_docs:
            if st.checkbox(
                doc["file_name"],
                key=f"quiz_chk_{doc['file_name']}",
                help=f"{doc.get('chunks', 0)} 个知识片段",
            ):
                selected.append(doc["file_name"])

        # 设置项
        col1, col2 = st.columns(2)
        with col1:
            num_questions = st.slider("题数", 3, 15, 5, key="quiz_num")
        with col2:
            difficulty = st.selectbox("难度", ["easy", "medium", "hard"], index=1, key="quiz_diff",
                                      format_func=lambda x: {"easy": "简单", "medium": "中等", "hard": "困难"}[x])

        # 题型选择
        qtypes = st.multiselect(
            "题型",
            ["choice", "fill", "short_answer"],
            default=["choice", "fill", "short_answer"],
            key="quiz_types",
            format_func=lambda x: {"choice": "选择题", "fill": "填空题", "short_answer": "简答题"}[x],
        )

        # 生成按钮
        if st.button("🎯 生成测验", use_container_width=True, type="primary", disabled=not selected, key="btn_gen_quiz"):
            _do_generate_quiz(rag, selected, num_questions, difficulty, qtypes)

        st.divider()

        # 渲染题目
        _render_quiz(rag)


def _get_available_docs(rag):
    """获取可选文档列表"""
    try:
        docs = rag.get_documents()
        return [
            {"file_name": d["file_name"], "id": d["id"], "chunks": d.get("chunks_count", 0)}
            for d in docs
            if d.get("status") == "ready"
        ]
    except Exception:
        return []


def _do_generate_quiz(rag, file_names, num_questions, difficulty, qtypes):
    """执行生成测验"""
    with st.spinner("正在出题..."):
        result = rag.generate_quiz(file_names, num_questions, difficulty, qtypes)

    if result["status"] == "success":
        st.session_state["_quiz_questions"] = result["questions"]
        st.session_state["_quiz_answers"] = {}
        st.session_state["_quiz_checked"] = {}
        st.success(result["message"])
    else:
        st.error(result["message"])


def _render_quiz(rag):
    """渲染测验题目"""
    questions = st.session_state.get("_quiz_questions")
    if not questions:
        st.caption("选择文件后点击生成测验")
        return

    answers = st.session_state.get("_quiz_answers", {})
    checked = st.session_state.get("_quiz_checked", {})

    for i, q in enumerate(questions):
        qtype = q.get("type", "short_answer")
        type_label = {"choice": "选择", "fill": "填空", "short_answer": "简答"}.get(qtype, "简答")
        q_key = f"quiz_q_{i}"

        with st.expander(f"第 {i + 1} 题 [{type_label}]", expanded=not checked.get(i)):
            st.markdown(f"**{q.get('question', '')}**")

            # 根据题型渲染输入
            if qtype == "choice":
                options = q.get("options", [])
                user_answer = st.radio(
                    "选择答案",
                    options,
                    key=q_key,
                    index=None,
                    label_visibility="collapsed",
                )
                if user_answer:
                    answers[i] = user_answer[0] if len(user_answer) > 1 else user_answer  # 取 A/B/C/D

            elif qtype == "fill":
                user_answer = st.text_input("填写答案", key=q_key, placeholder="输入答案...")
                if user_answer:
                    answers[i] = user_answer

            else:
                user_answer = st.text_area("作答", key=q_key, height=80, placeholder="输入你的回答...")
                if user_answer:
                    answers[i] = user_answer

            # 判分按钮
            if i not in checked:
                if st.button("✅ 提交答案", key=f"check_{i}", disabled=i not in answers):
                    result = rag.check_quiz_answer(q, answers.get(i, ""))
                    checked[i] = result
                    st.session_state["_quiz_checked"] = checked
                    st.rerun()
            else:
                result = checked[i]
                if result.get("correct"):
                    st.success(f"✅ 正确！{result.get('explanation', '')}")
                else:
                    st.error(f"❌ 错误。正确答案：{result.get('correct_answer', '')}")
                    if result.get("explanation"):
                        st.info(f"💡 {result['explanation']}")

    # 统计
    if checked:
        total = len(questions)
        correct_count = sum(1 for v in checked.values() if v.get("correct"))
        answered = len(checked)
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("已答", f"{answered}/{total}")
        with col2:
            st.metric("正确", f"{correct_count}/{answered}")
        with col3:
            rate = correct_count / answered if answered > 0 else 0
            st.metric("正确率", f"{rate:.0%}")

    # 操作按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 重新出题", use_container_width=True):
            st.session_state.pop("_quiz_questions", None)
            st.session_state.pop("_quiz_answers", None)
            st.session_state.pop("_quiz_checked", None)
            st.rerun()
    with col2:
        if st.button("🗑️ 清除测验", use_container_width=True):
            st.session_state.pop("_quiz_questions", None)
            st.session_state.pop("_quiz_answers", None)
            st.session_state.pop("_quiz_checked", None)
            st.rerun()

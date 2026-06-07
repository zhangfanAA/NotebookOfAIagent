"""
智能学习助手 — 学习统计仪表盘
负责: FULL

展示提问趋势、置信度分布、薄弱知识点排行等统计数据。
"""

import streamlit as st
from datetime import datetime, timedelta


def render_stats_page(rag):
    """渲染学习统计仪表盘"""
    st.markdown("### 📊 学习统计")

    sessions = rag.get_sessions()
    if not sessions:
        st.info("📭 暂无会话数据，请先开始对话")
        return

    # 会话选择
    session_options = {s.get("title", "新会话")[:30]: s["session_id"] for s in sessions}
    selected_title = st.selectbox("选择会话", list(session_options.keys()), key="stats_session")
    session_id = session_options[selected_title]

    st.divider()

    # 获取数据
    progress = rag.get_learning_progress(session_id)
    weak_topics = rag.get_weak_topics(session_id)
    messages = rag.get_session_history(session_id)

    # 顶部指标卡片
    _render_metrics(progress, messages)

    st.divider()

    # 图表区域
    col1, col2 = st.columns(2)
    with col1:
        _render_confidence_chart(messages)
    with col2:
        _render_topic_distribution(messages)

    st.divider()

    # 薄弱知识点
    _render_weak_topics(weak_topics)

    st.divider()

    # 提问趋势
    _render_question_trend(messages)


def _render_metrics(progress, messages):
    """渲染顶部指标"""
    user_msgs = [m for m in messages if m.get("role") == "user"]
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    confidences = [m.get("confidence", 0) for m in assistant_msgs if m.get("confidence") is not None]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("提问次数", len(user_msgs))
    with col2:
        st.metric("回答次数", len(assistant_msgs))
    with col3:
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        st.metric("平均置信度", f"{avg_conf:.0%}")
    with col4:
        total_questions = progress.get("total_questions", len(user_msgs))
        st.metric("累计提问", total_questions)


def _render_confidence_chart(messages):
    """渲染置信度分布图"""
    st.markdown("#### 置信度分布")
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    confidences = [m.get("confidence", 0) for m in assistant_msgs if m.get("confidence") is not None]

    if not confidences:
        st.caption("暂无置信度数据")
        return

    # 分段统计
    ranges = {"高 (≥70%)": 0, "中 (40-70%)": 0, "低 (<40%)": 0}
    for c in confidences:
        if c >= 0.7:
            ranges["高 (≥70%)"] += 1
        elif c >= 0.4:
            ranges["中 (40-70%)"] += 1
        else:
            ranges["低 (<40%)"] += 1

    st.bar_chart(ranges)


def _render_topic_distribution(messages):
    """渲染话题分布"""
    st.markdown("#### 话题分布")
    user_msgs = [m for m in messages if m.get("role") == "user"]

    if not user_msgs:
        st.caption("暂无提问数据")
        return

    # 简单关键词提取
    keywords = {}
    for m in user_msgs:
        content = m.get("content", "")
        # 取前 10 字作为话题标识
        topic = content[:10].strip()
        if topic:
            keywords[topic] = keywords.get(topic, 0) + 1

    # 取 top 10
    sorted_topics = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]
    if sorted_topics:
        chart_data = {k: v for k, v in sorted_topics}
        st.bar_chart(chart_data)


def _render_weak_topics(weak_topics):
    """渲染薄弱知识点"""
    st.markdown("#### 薄弱知识点排行")
    if not weak_topics:
        st.caption("暂无薄弱知识点数据")
        return

    for i, topic in enumerate(weak_topics):
        name = topic.get("topic", "未知")
        count = topic.get("question_count", 0)
        suggestion = topic.get("suggestion", "")

        with st.expander(f"{i + 1}. {name}（提问 {count} 次）", expanded=False):
            if suggestion:
                st.markdown(f"**建议：** {suggestion}")
            else:
                st.caption("暂无诊断建议")


def _render_question_trend(messages):
    """渲染提问趋势"""
    st.markdown("#### 提问趋势")
    user_msgs = [m for m in messages if m.get("role") == "user"]

    if not user_msgs:
        st.caption("暂无提问数据")
        return

    # 按日期统计
    daily_counts = {}
    for m in user_msgs:
        created = m.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_str = dt.strftime("%m-%d")
            except (ValueError, AttributeError):
                date_str = "未知"
        else:
            date_str = "未知"
        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1

    if daily_counts:
        st.bar_chart(daily_counts)

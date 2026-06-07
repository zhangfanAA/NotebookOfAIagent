"""
智能学习助手 — Streamlit 前端入口
负责: FULL

布局：左侧边栏（会话/上传）+ 中间聊天区 + 右侧思维导图栏（可收起）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from src.rag.rag_service import RAGService
from src.frontend.components import get_theme_css
from src.frontend.sidebar import render_sidebar
from src.frontend.chat import render_main_area
from src.frontend.mindmap import render_mindmap_panel
from src.frontend.quiz import render_quiz_panel
from src.frontend.flashcard import render_flashcard_panel
from src.frontend.stats import render_stats_page
from src.frontend.compare import render_compare_panel


@st.cache_resource
def init_rag_service():
    return RAGService()


def main():
    st.set_page_config(page_title="智能学习助手", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False
    if "show_mindmap" not in st.session_state:
        st.session_state["show_mindmap"] = False
    if "show_quiz" not in st.session_state:
        st.session_state["show_quiz"] = False
    if "show_flashcard" not in st.session_state:
        st.session_state["show_flashcard"] = False
    if "show_stats" not in st.session_state:
        st.session_state["show_stats"] = False
    if "show_compare" not in st.session_state:
        st.session_state["show_compare"] = False

    rag = init_rag_service()
    render_sidebar(rag)
    st.markdown(get_theme_css(st.session_state["dark_mode"]), unsafe_allow_html=True)

    # 主区域布局
    show_full_page = st.session_state["show_stats"] or st.session_state["show_compare"]
    show_right = st.session_state["show_mindmap"] or st.session_state["show_quiz"] or st.session_state["show_flashcard"]

    if show_full_page:
        # 全页面面板（统计/对比）— 不渲染聊天区
        if st.session_state["show_stats"]:
            render_stats_page(rag)
        else:
            render_compare_panel(rag)
    elif show_right:
        # 右侧面板 + 聊天区
        col_chat, col_right = st.columns([3, 2], gap="medium")
        with col_chat:
            render_main_area(rag)
        with col_right:
            if st.session_state["show_quiz"]:
                render_quiz_panel(rag)
            elif st.session_state["show_flashcard"]:
                render_flashcard_panel(rag)
            else:
                render_mindmap_panel(rag)
    else:
        # 仅聊天区
        render_main_area(rag)


if __name__ == "__main__":
    main()

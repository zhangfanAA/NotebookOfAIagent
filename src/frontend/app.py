"""
智能学习助手 — Streamlit 前端入口
负责: FULL

精简入口，功能已拆分至:
- components.py  — 可复用 UI 组件
- export.py      — 导出功能
- sidebar.py     — 侧边栏渲染
- chat.py        — 主聊天区域
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from src.rag.rag_service import RAGService
from src.frontend.components import get_theme_css
from src.frontend.sidebar import render_sidebar
from src.frontend.chat import render_main_area


@st.cache_resource
def init_rag_service():
    return RAGService()


def main():
    st.set_page_config(page_title="智能学习助手", page_icon="📚", layout="wide", initial_sidebar_state="expanded")
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False
    rag = init_rag_service()
    render_sidebar(rag)
    st.markdown(get_theme_css(st.session_state["dark_mode"]), unsafe_allow_html=True)
    render_main_area(rag)


if __name__ == "__main__":
    main()

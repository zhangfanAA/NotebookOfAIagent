"""
智能学习助手 — 可复用 UI 组件
负责: FULL

包含: 来源展示、LaTeX 渲染、主题 CSS、错误处理、健康检查
"""

import streamlit as st


def get_friendly_error(error_msg: str) -> str:
    """将技术错误转换为用户友好的提示"""
    error_lower = str(error_msg).lower()
    if "timeout" in error_lower or "超时" in error_lower:
        return "回答生成超时，请稍后重试。如果问题较长，请尝试简化问题。"
    if "rate limit" in error_lower or "429" in error_lower:
        return "请求过于频繁，请稍等几秒后重试。"
    if "connection" in error_lower or "连接" in error_lower:
        return "网络连接失败，请检查网络设置。"
    if "api key" in error_lower or "认证" in error_lower:
        return "API 认证失败，请检查配置。"
    if "empty" in error_lower or "空" in error_lower:
        return "问题不能为空，请输入你的问题。"
    return f"出错了: {error_msg}"


def render_latex_content(content: str):
    """渲染包含 LaTeX 公式的内容"""
    import re
    content = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', content, flags=re.DOTALL)
    content = re.sub(r'\\\((.+?)\\\)', r'$\1$', content)
    st.markdown(content)


def get_theme_css(dark_mode):
    """获取主题 CSS"""
    base_css = """
@media (max-width: 768px) {
    .stColumn { flex: 1 1 100% !important; width: 100% !important; }
    .stButton > button { width: 100%; }
    section[data-testid="stSidebar"] { width: 100% !important; }
}
pre code { border-radius: 8px; padding: 12px; }
"""
    if dark_mode:
        return f"""<style>
.source-box {{ background: #1e3a5f; border-left: 4px solid #60a5fa; padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 0.9em; color: #e2e8f0; }}
.confidence-high {{ color: #4ade80; }} .confidence-mid {{ color: #facc15; }} .confidence-low {{ color: #f87171; }}
.diagnosis-card {{ background: linear-gradient(135deg, #7c3aed22, #2563eb22); border: 1px solid #7c3aed55; border-radius: 10px; padding: 12px; margin: 8px 0; }}
.diagnosis-title {{ color: #a78bfa; font-weight: bold; margin-bottom: 4px; }}
.diagnosis-text {{ color: #cbd5e1; font-size: 0.9em; }}
{base_css}
</style>"""
    return f"""<style>
.source-box {{ background: #f0f7ff; border-left: 4px solid #3b82f6; padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 0.9em; }}
.confidence-high {{ color: #16a34a; }} .confidence-mid {{ color: #ca8a04; }} .confidence-low {{ color: #dc2626; }}
.diagnosis-card {{ background: linear-gradient(135deg, #ede9fe, #dbeafe); border: 1px solid #c4b5fd; border-radius: 10px; padding: 12px; margin: 8px 0; }}
.diagnosis-title {{ color: #7c3aed; font-weight: bold; margin-bottom: 4px; }}
.diagnosis-text {{ color: #475569; font-size: 0.9em; }}
{base_css}
</style>"""


def render_sources(sources, confidence=None):
    """渲染引用来源"""
    if not sources:
        return
    conf_text = ""
    if confidence is not None:
        if confidence >= 0.7:
            label = "高置信"
        elif confidence >= 0.4:
            label = "中置信"
        else:
            label = "低置信"
        conf_text = f" [{label} {confidence:.0%}]"
    with st.expander(f"📖 引用来源 ({len(sources)}){conf_text}", expanded=False):
        for i, src in enumerate(sources):
            sn = src.get("source", "?")
            pg = src.get("page", "?")
            sc = src.get("score", 0)
            full_content = src.get("content", "")
            preview = full_content[:150]
            st.markdown(
                f'<div class="source-box"><strong>{i + 1}. {sn} 第{pg}页</strong> (相关度 {sc:.0%})<br>'
                f'<span style="color:#888">{preview}</span></div>',
                unsafe_allow_html=True,
            )
            if len(full_content) > 150:
                with st.expander(f"展开完整内容 [{i+1}]", expanded=False):
                    st.text(full_content)


def render_health_check():
    """系统健康检查"""
    st.subheader("🩺 系统状态")
    checks = []

    # MySQL
    try:
        from src.database.db_manager import DBManager
        db = DBManager()
        conn = db.get_connection()
        conn.close()
        checks.append(("MySQL", True))
    except Exception:
        checks.append(("MySQL", False))

    # Chroma 向量库
    try:
        from src.data.vector_store import get_collection
        col = get_collection()
        col.count()
        checks.append(("Chroma", True))
    except Exception:
        checks.append(("Chroma", False))

    # DeepSeek API
    try:
        from src.rag.llm_client import LLMClient
        client = LLMClient()
        checks.append(("DeepSeek API", bool(client._deepseek_key)))
    except Exception:
        checks.append(("DeepSeek API", False))

    # Ollama
    try:
        import urllib.request
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        checks.append(("Ollama", req.status == 200))
    except Exception:
        checks.append(("Ollama", False))

    for name, ok in checks:
        icon = "🟢" if ok else "🔴"
        st.caption(f"{icon} {name}")

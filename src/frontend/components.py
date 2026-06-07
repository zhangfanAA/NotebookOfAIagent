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
    """获取主题 CSS（Apple 风格 · 淡蓝色系）"""
    font = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Arial, sans-serif'
    base = f"""
/* ===== Apple 风格 · 淡蓝色系 ===== */
.stApp {{
    font-family: {font};
}}
section[data-testid="stSidebar"] {{
    background: rgba(240, 248, 255, 0.85) !important;
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border-right: 1px solid rgba(100, 180, 240, 0.15);
}}
.stButton > button {{
    border-radius: 999px;
    font-family: {font};
    font-weight: 500;
    border: none;
    transition: all 0.2s ease;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(100, 180, 240, 0.2);
}}
div[data-testid="stExpander"] {{
    border-radius: 16px !important;
    border: 1px solid rgba(100, 180, 240, 0.12) !important;
    box-shadow: 0 2px 8px rgba(100, 180, 240, 0.06);
}}
div[data-testid="stMetric"] {{
    background: #fff;
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: 0 2px 12px rgba(100, 180, 240, 0.08);
}}
div[data-testid="stTabs"] {{
    font-family: {font};
}}
div[data-baseweb="tab"] {{
    font-family: {font};
    font-weight: 500;
}}
pre code {{
    border-radius: 12px;
    padding: 16px;
}}
div[data-testid="stChatMessage"] {{
    border-radius: 20px;
    padding: 16px 20px;
    margin: 8px 0;
}}
@media (max-width: 768px) {{
    .stColumn {{ flex: 1 1 100% !important; width: 100% !important; }}
    .stButton > button {{ width: 100%; }}
    section[data-testid="stSidebar"] {{ width: 100% !important; }}
}}
"""
    if dark_mode:
        return f"""<style>
/* 深色模式 · 淡蓝色调 */
.stApp {{ background: #1a2332; color: #e8f0fe; }}
section[data-testid="stSidebar"] {{ background: rgba(30, 50, 70, 0.88) !important; border-right: 1px solid rgba(100,180,240,0.12); }}
.stButton > button {{ background: #5ac8fa; color: #1a2332; }}
.stButton > button:hover {{ background: #7dd3fc; }}
div[data-testid="stMetric"] {{ background: #1e3248; }}
div[data-testid="stExpander"] {{ border-color: rgba(100,180,240,0.12) !important; background: #1e3248; }}
.source-box {{ background: #1e3248; border-left: 4px solid #5ac8fa; padding: 10px 14px; margin: 6px 0; border-radius: 12px; font-size: 0.9em; color: #e8f0fe; }}
.confidence-high {{ color: #4ade80; }} .confidence-mid {{ color: #facc15; }} .confidence-low {{ color: #f87171; }}
.diagnosis-card {{ background: linear-gradient(135deg, #1e324822, #2563eb22); border: 1px solid #5ac8fa55; border-radius: 16px; padding: 16px; margin: 8px 0; }}
.diagnosis-title {{ color: #5ac8fa; font-weight: 600; margin-bottom: 4px; }}
.diagnosis-text {{ color: #b0c4de; font-size: 0.9em; }}
.gen-card {{ background: #1e3248; border-radius: 20px; padding: 24px; box-shadow: 0 4px 24px rgba(0,0,0,0.3); margin: 16px 0; }}
{base}
</style>"""
    return f"""<style>
/* 浅色模式 · 淡蓝色系 */
.stApp {{ background: #f0f7ff; color: #1d1d1f; }}
.stButton > button {{ background: #5ac8fa; color: #fff; }}
.stButton > button:hover {{ background: #7dd3fc; }}
.source-box {{ background: #e8f4fd; border-left: 4px solid #5ac8fa; padding: 10px 14px; margin: 6px 0; border-radius: 12px; font-size: 0.9em; }}
.confidence-high {{ color: #16a34a; }} .confidence-mid {{ color: #ca8a04; }} .confidence-low {{ color: #dc2626; }}
.diagnosis-card {{ background: linear-gradient(135deg, #e8f4fd, #dbeafe); border: 1px solid #93c5fd; border-radius: 16px; padding: 16px; margin: 8px 0; }}
.diagnosis-title {{ color: #2563eb; font-weight: 600; margin-bottom: 4px; }}
.diagnosis-text {{ color: #475569; font-size: 0.9em; }}
.gen-card {{ background: #ffffff; border-radius: 20px; padding: 24px; box-shadow: 0 4px 24px rgba(100, 180, 240, 0.1); margin: 16px 0; }}
{base}
</style>"""


def render_error_toast(message: str, details: str = ""):
    """渲染错误提示弹窗"""
    st.markdown(
        f'''<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:12px;padding:12px 16px;margin:8px 0;">
        <strong style="color:#dc2626;">⚠️ 出错了</strong><br>
        <span style="color:#991b1b;font-size:0.9em;">{message}</span>
        {f'<br><span style="color:#991b1b;font-size:0.8em;opacity:0.7;">{details}</span>' if details else ''}
        </div>''',
        unsafe_allow_html=True,
    )


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
    """系统健康检查（懒加载：仅展开时执行）"""
    with st.expander("🩺 系统状态", expanded=False):
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

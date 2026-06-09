"""
智能学习助手 — 导出功能
负责: FULL

包含: Markdown 导出、HTML 导出
"""

from datetime import datetime


def generate_export_md(messages):
    """生成 Markdown 格式的导出"""
    lines = [f"# 对话导出 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"## 问: {content}\n")
        else:
            lines.append(f"## 答: {content}\n")
            conf = msg.get("confidence")
            if conf is not None:
                lines.append(f"置信度: {conf:.0%}\n")
            sources = msg.get("sources")
            if sources:
                lines.append("### 引用来源\n")
                for j, s in enumerate(sources):
                    lines.append(f"{j + 1}. {s.get('source', '?')} 第{s.get('page', '?')}页 ({s.get('score', 0):.0%})\n")
        lines.append("---\n")
    return "\n".join(lines)


def generate_export_html(messages):
    """生成 HTML 格式的导出"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>对话导出</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
.user-msg {{ background: #e3f2fd; padding: 12px; border-radius: 8px; margin: 10px 0; }}
.assistant-msg {{ background: #f5f5f5; padding: 12px; border-radius: 8px; margin: 10px 0; }}
.source {{ font-size: 0.9em; color: #666; margin: 5px 0; }}
.confidence {{ font-size: 0.85em; color: #888; }}
h1 {{ color: #1976d2; }}
</style></head><body>
<h1>对话导出</h1><p>导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            html += f'<div class="user-msg"><strong>问:</strong> {content}</div>\n'
        else:
            html += f'<div class="assistant-msg"><strong>答:</strong> {content}</div>\n'
            conf = msg.get("confidence")
            if conf is not None:
                html += f'<p class="confidence">置信度: {conf:.0%}</p>\n'
            sources = msg.get("sources")
            if sources:
                html += '<div class="source"><strong>引用来源:</strong><ul>'
                for s in sources:
                    html += f'<li>{s.get("source", "?")} 第{s.get("page", "?")}页 ({s.get("score", 0):.0%})</li>'
                html += '</ul></div>\n'
    html += '</body></html>'
    return html

"""
智能学习助手 — 思维导图右侧面板
负责: FULL

右侧可收起的思维导图/笔记生成面板。
graph LR 树形结构（根在左，叶在右）+ 点击节点列表 → 聊天区解释。
"""

import re
import streamlit as st
import streamlit.components.v1 as components


def render_mindmap_panel(rag):
    """渲染右侧思维导图面板"""
    with st.container():
        st.markdown("### 🗺️ 智能笔记")

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
                key=f"mp_chk_{doc['file_name']}",
                help=f"{doc.get('chunks', 0)} 个知识片段",
            ):
                selected.append(doc["file_name"])

        # 提示词
        user_prompt = st.text_input(
            "强化提示词",
            "",
            placeholder="例如：重点提取算法的时间复杂度",
            key="mp_prompt",
        )

        # 生成按钮
        col1, col2 = st.columns(2)
        with col1:
            btn_map = st.button("🗺️ 导图", use_container_width=True, type="primary", disabled=not selected, key="btn_gen_map")
        with col2:
            btn_notes = st.button("📝 笔记", use_container_width=True, disabled=not selected, key="btn_gen_notes")

        if btn_map:
            _do_generate(rag, selected, user_prompt, "mindmap")
        if btn_notes:
            _do_generate(rag, selected, user_prompt, "notes")

        st.divider()

        # 显示结果
        _render_result(rag)


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


def _do_generate(rag, file_names, user_prompt, output_type):
    """执行生成"""
    with st.spinner("生成中..."):
        result = rag.generate_content(file_names, user_prompt, output_type)

    if result["status"] == "success":
        st.success(result["message"])
        result["source_files"] = file_names
        st.session_state["_gen_result"] = result
    else:
        st.error(result["message"])


def _render_result(rag):
    """渲染生成结果"""
    result = st.session_state.get("_gen_result")
    if not result:
        st.caption("选择文件后点击生成")
        return

    output_type = result.get("type", "mindmap")

    if output_type == "mindmap" and result.get("mermaid_code"):
        mermaid_code = result["mermaid_code"]
        _render_mermaid_tree(mermaid_code)

        # 提取节点并显示可点击列表
        nodes = _extract_mermaid_nodes(mermaid_code)
        if nodes:
            _render_node_list(nodes)

        with st.expander("📄 完整文本", expanded=False):
            st.markdown(result["content"])
    else:
        st.markdown(result.get("content", ""))

    # 下载 + 清除
    col1, col2 = st.columns(2)
    with col1:
        md = _build_download(result)
        st.download_button("📥 下载", data=md, file_name="笔记.md", mime="text/markdown", use_container_width=True)
    with col2:
        if st.button("🗑️ 清除", use_container_width=True):
            st.session_state.pop("_gen_result", None)
            st.rerun()


def _render_node_list(nodes: list):
    """渲染可点击的节点列表"""
    st.markdown("---")
    st.markdown("**💡 点击节点查看解释**")

    def _on_node_click(topic):
        """节点点击回调：设置待处理输入，由主聊天区处理"""
        st.session_state["_pending_input"] = f"请详细解释「{topic}」这个知识点"

    # 使用 columns 布局节点按钮
    cols_per_row = 3
    for i in range(0, len(nodes), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(nodes):
                node = nodes[idx]
                with col:
                    st.button(
                        node,
                        key=f"node_btn_{idx}",
                        use_container_width=True,
                        type="secondary",
                        on_click=_on_node_click,
                        args=(node,),
                    )


def _render_mermaid_tree(mermaid_code: str):
    """渲染 graph LR 树形思维导图（静态展示）"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
                margin: 0;
                padding: 12px;
                background: transparent;
                overflow-x: auto;
            }}
            .mermaid svg {{
                min-width: 100%;
                height: auto;
            }}
            .mermaid .node rect {{
                cursor: pointer;
                transition: all 0.15s ease;
                rx: 8;
                ry: 8;
            }}
            .mermaid .node:hover rect {{
                filter: brightness(0.92);
                stroke-width: 2.5px;
            }}
            .mermaid .edgePath .path {{
                stroke: #93c5fd;
                stroke-width: 1.5px;
            }}
            .mermaid .node text {{
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <pre class="mermaid">{mermaid_code}</pre>
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'base',
                securityLevel: 'loose',
                themeVariables: {{
                    primaryColor: '#dbeafe',
                    primaryBorderColor: '#93c5fd',
                    primaryTextColor: '#1e3a5f',
                    lineColor: '#93c5fd',
                    secondaryColor: '#eff6ff',
                    tertiaryColor: '#ffffff',
                    fontFamily: '-apple-system, BlinkMacSystemFont, SF Pro Text, Helvetica Neue, sans-serif',
                    fontSize: '13px',
                }},
            }});
        </script>
    </body>
    </html>
    """
    components.html(html, height=500, scrolling=True)


def _extract_mermaid_nodes(mermaid_code: str) -> list:
    """从 graph LR 代码中提取节点文本（叶子节点优先）"""
    lines = mermaid_code.split('\n')

    # 提取所有节点: A["text"] / A['text'] / A((text)) / A[裸文本]
    node_label_map = {}
    pat_sq = re.compile(r'''(\w+)\s*\[("[^"]*"|'[^']*')\]''')
    pat_round = re.compile(r'''(\w+)\s*\(\s*("[^"]*"|'[^']*')\s*\)''')
    pat_double = re.compile(r'''(\w+)\s*\(\(\s*("[^"]*"|'[^']*')\s*\)\)''')
    pat_bare = re.compile(r'(\w+)\[([^\]\"]+)\]')

    for line in lines:
        for m in pat_double.finditer(line):
            node_label_map[m.group(1)] = m.group(2).strip("\"'")
        for m in pat_sq.finditer(line):
            if m.group(1) not in node_label_map:
                node_label_map[m.group(1)] = m.group(2).strip("\"'")
        for m in pat_round.finditer(line):
            if m.group(1) not in node_label_map:
                node_label_map[m.group(1)] = m.group(2).strip("\"'")
        for m in pat_bare.finditer(line):
            if m.group(1) not in node_label_map:
                node_label_map[m.group(1)] = m.group(2).strip()

    # 提取所有边: A --> B，找出所有父节点
    edge_pattern = re.compile(r'(\w+)\s*-->\s*(\w+)')
    parent_nodes = set()
    for line in lines:
        for m in edge_pattern.finditer(line):
            parent_nodes.add(m.group(1))

    # 叶子节点 = 有标签但不是任何边的父节点
    leaf_nodes = [node_label_map[nid] for nid in node_label_map if nid not in parent_nodes]

    # 如果没有叶子节点，返回所有节点
    if not leaf_nodes:
        return list(set(node_label_map.values()))

    return leaf_nodes


def _build_download(result: dict) -> str:
    """构建下载内容"""
    output_type = result.get("type", "")
    mermaid = result.get("mermaid_code")
    content = result.get("content", "")

    if output_type == "mindmap" and mermaid:
        return f"# 思维导图\n\n```mermaid\n{mermaid}\n```\n\n---\n\n{content}"
    return content

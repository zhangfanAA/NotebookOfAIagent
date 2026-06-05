"""
智能学习助手 — 文本分块策略
负责: RAG
任务: TASK-DATA-003

语义感知的文本分块，支持按标题、段落、句子多级切分。
每块附加唯一 chunk_id 和完整元数据。
"""

import hashlib
from typing import List

from src.config import get_config
from src.logger import get_logger

logger = get_logger("data.chunker")

# 分割符优先级（从大语义单元到小语义单元）
SEPARATORS = [
    "\n## ",       # Markdown 二级标题
    "\n### ",      # Markdown 三级标题
    "\n#### ",     # Markdown 四级标题
    "\n\n",        # 段落
    "\n",          # 行
    "。",          # 中文句号
    "；",          # 中文分号
    ". ",          # 英文句号
    "! ",          # 英文感叹号
    "? ",          # 英文问号
]


def chunk_text(
    text: str,
    source: str,
    page: int,
    file_type: str = "pdf",
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[dict]:
    """
    将单页文本切分为多个语义块

    Args:
        text: 待分块的文本
        source: 来源文件名
        page: 页码
        file_type: 文件类型
        chunk_size: 块大小（字符数），默认从配置读取
        chunk_overlap: 块重叠大小，默认从配置读取

    Returns:
        [
            {
                "content": str,
                "chunk_id": str,       # 唯一标识
                "source": str,
                "page": int,
                "file_type": str
            }
        ]
    """
    config = get_config()["chunking"]
    if chunk_size is None:
        chunk_size = config["chunk_size"]
    if chunk_overlap is None:
        chunk_overlap = config["chunk_overlap"]

    if not text or not text.strip():
        return []

    # 递归文本分割
    chunks_content = _recursive_split(text, chunk_size, chunk_overlap, SEPARATORS)

    # 构造完整 chunk 对象
    chunks = []
    for i, content in enumerate(chunks_content):
        content = content.strip()
        if not content:
            continue
        chunk_id = _generate_chunk_id(source, page, i)
        chunks.append({
            "content": content,
            "chunk_id": chunk_id,
            "source": source,
            "page": page,
            "file_type": file_type,
        })

    logger.debug("分块完成: %s page=%d → %d chunks", source, page, len(chunks))
    return chunks


def chunk_pages(pages: list) -> list:
    """
    批量处理多页文本

    Args:
        pages: pdf_parser.parse_pdf() 的输出

    Returns:
        所有页的分块结果合并列表
    """
    all_chunks = []
    for page_data in pages:
        chunks = chunk_text(
            text=page_data["content"],
            source=page_data["source"],
            page=page_data["page"],
            file_type=page_data.get("file_type", "pdf"),
        )
        all_chunks.extend(chunks)
    logger.info("批量分块完成: %d 页 → %d chunks", len(pages), len(all_chunks))
    return all_chunks


def _recursive_split(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list,
) -> list:
    """
    递归文本分割算法

    按照 separators 的优先级依次尝试切分：
    1. 先用最高优先级的分割符切分
    2. 如果某个片段仍然超过 chunk_size，用下一级分割符继续切分
    3. 最终如果仍然超过，硬切
    """
    if len(text) <= chunk_size:
        return [text]

    # 找到当前可用的分割符
    separator = separators[0] if separators else ""
    remaining_separators = separators[1:] if len(separators) > 1 else []

    # 按分割符切分
    if separator:
        parts = text.split(separator)
    else:
        # 无更多分割符，硬切
        parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    # 合并小块、递归切分大块
    result = []
    current_chunk = ""

    for part in parts:
        candidate = (current_chunk + separator + part) if current_chunk else part

        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            # 保存当前块
            if current_chunk:
                result.append(current_chunk)

            # 当前 part 本身是否超长
            if len(part) <= chunk_size:
                current_chunk = part
            else:
                # 递归用下一级分割符切分
                sub_chunks = _recursive_split(part, chunk_size, chunk_overlap, remaining_separators)
                result.extend(sub_chunks)
                current_chunk = ""

    if current_chunk:
        result.append(current_chunk)

    # 添加重叠
    if chunk_overlap > 0 and len(result) > 1:
        result = _add_overlap(result, chunk_overlap)

    return result


def _add_overlap(chunks: list, overlap: int) -> list:
    """给相邻块添加重叠文本"""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:]
        result.append(prev_tail + chunks[i])
    return result


def _generate_chunk_id(source: str, page: int, index: int) -> str:
    """生成唯一 chunk ID"""
    raw = f"{source}_{page}_{index}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"{source.replace(' ', '_')}_p{page}_{index}_{short_hash}"

"""可选 LLM 实体抽取。"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.edges import _as_str_list, weak_keywords_from_text

EXTRACT_PROMPT = """你是知识图谱实体抽取助手。从下面文本中提取关键实体（人名、组织、地点、产品、概念）。
只输出 JSON 数组，不要其它说明。例如：["实体A","实体B"]

文本：
{text}
"""


def extract_entities_with_llm(llm: Any, text: str) -> list[str]:
    if llm is None:
        return []
    prompt = EXTRACT_PROMPT.format(text=text[:4000])
    try:
        if hasattr(llm, "invoke"):
            result = llm.invoke(prompt)
        elif callable(llm):
            result = llm(prompt)
        else:
            return []
        content = getattr(result, "content", result)
        if isinstance(content, list):
            # some chat models return list of blocks
            content = "".join(str(getattr(c, "text", c)) for c in content)
        content = str(content).strip()
        match = re.search(r"\[.*\]", content, flags=re.DOTALL)
        payload = match.group(0) if match else content
        parsed = json.loads(payload)
        return _as_str_list(parsed)
    except Exception:  # noqa: BLE001
        return []


def enrich_documents_for_graph(
    documents: list[Document],
    *,
    edge_fields: list[str],
    graph_mode: str,
    llm: Any | None = None,
) -> list[Document]:
    """为入库文档补齐 entities/keywords 等边字段。"""
    enriched: list[Document] = []
    for doc in documents:
        meta = dict(doc.metadata or {})
        if graph_mode == "LLM抽取实体写入边" and llm is not None:
            entities = extract_entities_with_llm(llm, doc.page_content)
            if entities:
                meta["entities"] = entities
        # 若仍无 entities，用弱关键词兜底，保证图边可用
        if "entities" in edge_fields and not _as_str_list(meta.get("entities")):
            meta["entities"] = weak_keywords_from_text(doc.page_content)
        if "keywords" in edge_fields and not _as_str_list(meta.get("keywords")):
            meta["keywords"] = weak_keywords_from_text(doc.page_content, limit=6)
        enriched.append(Document(page_content=doc.page_content, metadata=meta, id=doc.id))
    return enriched

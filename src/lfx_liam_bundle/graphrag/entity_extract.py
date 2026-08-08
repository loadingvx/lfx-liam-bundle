"""兼容入口：完整抽取见 extract_graph；此处保留旧 metadata 富化函数供测试/遗留调用。"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.edges import normalize_edge_metadata, weak_keywords_from_text
from lfx_liam_bundle.graphrag.extract_graph import (
    DEFAULT_ENTITY_TYPES,
    extract_from_text_unit,
    extract_graph_from_units,
    merge_graph_primitives,
)


def enrich_documents_for_graph(
    documents: list[Document],
    *,
    edge_fields: list[str] | None = None,
    graph_mode: str = "仅用已有metadata边",
    llm: Any | None = None,
) -> list[Document]:
    """遗留：为 metadata 边填充 entities/keywords。

    完整 GraphRAG 请使用 ``pipeline.run_indexing_pipeline``（实体+关系+Gleaning+社区）。
    """
    _ = llm, graph_mode
    fields = edge_fields or ["entities", "keywords"]
    out: list[Document] = []
    for doc in documents:
        meta = dict(doc.metadata or {})
        meta = normalize_edge_metadata(meta, fields)
        if "entities" in fields and not meta.get("entities"):
            meta["entities"] = weak_keywords_from_text(doc.page_content or "")
        if "keywords" in fields and not meta.get("keywords"):
            meta["keywords"] = list(
                meta.get("entities") or weak_keywords_from_text(doc.page_content or "")
            )
        out.append(Document(page_content=doc.page_content, metadata=meta, id=doc.id))
    return out


__all__ = [
    "DEFAULT_ENTITY_TYPES",
    "enrich_documents_for_graph",
    "extract_from_text_unit",
    "extract_graph_from_units",
    "merge_graph_primitives",
]

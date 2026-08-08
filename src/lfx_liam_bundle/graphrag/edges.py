"""边定义解析与 metadata 规范化（对齐 DataStax GraphRetriever 语义）。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from langchain_core.documents import Document
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.types import DEFAULT_EDGE_DEFINITION


def parse_edge_definition(edge_definition: str | None) -> tuple[str, ...]:
    raw = (edge_definition or DEFAULT_EDGE_DEFINITION).strip()
    if not raw:
        msg = "边定义不能为空。示例：entities,entities 或 mentions,Id()"
        raise ValueError(msg)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != 2:
        msg = f"边定义必须是「源字段,目标字段」两个部分，当前为：{raw!r}"
        raise ValueError(msg)
    return (parts[0], parts[1])


def evaluate_edge_definition(edge_definition: str | None) -> tuple:
    """转换为 GraphRetriever 可用的 edge tuple（支持 Id()）。"""
    from graph_retriever.edges.metadata import Id

    source, target = parse_edge_definition(edge_definition)
    evaluated = []
    for value in (source, target):
        if value in {"Id()", "$id"}:
            evaluated.append(Id())
        else:
            evaluated.append(value)
    return tuple(evaluated)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,;|，、\n]+", value)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_as_str_list(item))
        return out
    return [str(value).strip()] if str(value).strip() else []


def normalize_edge_metadata(
    metadata: dict[str, Any] | None, edge_fields: list[str]
) -> dict[str, Any]:
    meta = dict(metadata or {})
    for field in edge_fields:
        if field in meta:
            values = _as_str_list(meta.get(field))
            # 去重保序
            seen: set[str] = set()
            unique: list[str] = []
            for v in values:
                key = v.casefold()
                if key not in seen:
                    seen.add(key)
                    unique.append(v)
            meta[field] = unique
    return meta


def stable_doc_id(
    text: str, metadata: dict[str, Any] | None = None, explicit_id: str | None = None
) -> str:
    if explicit_id:
        return str(explicit_id)
    meta = metadata or {}
    for key in ("doc_id", "id", "_id"):
        if meta.get(key):
            return str(meta[key])
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def coerce_documents(ingest_data: Any) -> list[Document]:
    """将 Langflow Data/Document/str 列表规范为 Document。"""
    if ingest_data is None:
        return []
    items = ingest_data if isinstance(ingest_data, list) else [ingest_data]
    documents: list[Document] = []
    for item in items:
        if isinstance(item, Document):
            text = (item.page_content or "").strip()
            if not text:
                continue
            meta = normalize_edge_metadata(item.metadata, ["entities", "keywords", "mentions"])
            doc_id = stable_doc_id(text, meta, explicit_id=meta.get("doc_id"))
            meta["doc_id"] = doc_id
            documents.append(Document(page_content=text, metadata=meta, id=doc_id))
            continue
        if isinstance(item, Data):
            text = (item.get_text() if hasattr(item, "get_text") else None) or item.text or ""
            if not text and isinstance(item.data, dict):
                text = str(item.data.get("text") or item.data.get("content") or "")
            text = text.strip()
            if not text:
                continue
            meta = dict(item.data) if isinstance(item.data, dict) else {}
            meta = normalize_edge_metadata(meta, ["entities", "keywords", "mentions"])
            doc_id = stable_doc_id(text, meta, explicit_id=meta.get("doc_id"))
            meta["doc_id"] = doc_id
            documents.append(Document(page_content=text, metadata=meta, id=doc_id))
            continue
        if isinstance(item, str) and item.strip():
            text = item.strip()
            doc_id = stable_doc_id(text)
            documents.append(Document(page_content=text, metadata={"doc_id": doc_id}, id=doc_id))
            continue
        if isinstance(item, dict):
            text = str(
                item.get("text") or item.get("page_content") or item.get("content") or ""
            ).strip()
            if not text:
                continue
            meta = normalize_edge_metadata(item, ["entities", "keywords", "mentions"])
            doc_id = stable_doc_id(text, meta, explicit_id=meta.get("doc_id") or meta.get("id"))
            meta["doc_id"] = doc_id
            documents.append(Document(page_content=text, metadata=meta, id=doc_id))
    return documents


def weak_keywords_from_text(text: str, limit: int = 8) -> list[str]:
    """无 LLM 时的弱边：抽取较长的词/字片段作为 keywords。"""
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text or "")
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokens:
        key = tok.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
        if len(out) >= limit:
            break
    return out

"""文档规范化：将上游 Data/Document 转为 TextUnit 可用的 Document 列表。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from langchain_core.documents import Document
from lfx.schema.data import Data


def stable_doc_id(
    text: str, metadata: dict[str, Any] | None = None, explicit_id: str | None = None
) -> str:
    if explicit_id:
        return str(explicit_id)
    meta = metadata or {}
    for key in ("doc_id", "id", "_id"):
        if meta.get(key):
            return str(meta[key])
    digest = hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:16]  # noqa: S324
    return f"tu_{digest}"


def coerce_documents(ingest_data: Any) -> list[Document]:
    """把组件输入统一成 langchain Document 列表（跳过空文本）。"""
    if ingest_data is None:
        return []
    items = ingest_data if isinstance(ingest_data, list) else [ingest_data]
    docs: list[Document] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, Document):
            text = (item.page_content or "").strip()
            if not text:
                continue
            meta = dict(item.metadata or {})
            uid = str(item.id or meta.get("doc_id") or stable_doc_id(text, meta))
            meta["doc_id"] = uid
            docs.append(Document(page_content=text, metadata=meta, id=uid))
            continue
        if isinstance(item, Data):
            text = (item.text or "").strip()
            if not text and isinstance(item.data, dict):
                text = str(item.data.get("text") or item.data.get("content") or "").strip()
            if not text:
                continue
            meta = dict(item.data) if isinstance(item.data, dict) else {}
            uid = str(meta.get("doc_id") or meta.get("id") or stable_doc_id(text, meta))
            meta["doc_id"] = uid
            docs.append(Document(page_content=text, metadata=meta, id=uid))
            continue
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("page_content") or item.get("content") or "").strip()
            if not text:
                continue
            meta = {k: v for k, v in item.items() if k not in {"text", "page_content", "content"}}
            uid = str(item.get("doc_id") or item.get("id") or stable_doc_id(text, meta))
            meta["doc_id"] = uid
            docs.append(Document(page_content=text, metadata=meta, id=uid))
            continue
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            uid = stable_doc_id(text)
            docs.append(Document(page_content=text, metadata={"doc_id": uid}, id=uid))
    return docs


def weak_keywords_from_text(text: str, *, limit: int = 12) -> list[str]:
    """简单分词（仅供测试辅助，不参与 GraphRAG 主路径）。"""
    parts = re.findall(r"[\w\u4e00-\u9fff]{2,}", text or "")
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out

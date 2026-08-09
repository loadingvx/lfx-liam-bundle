"""Phase 1：按 token 将 Document 切为 TextUnit（对齐微软默认 ~1200 / overlap）。"""

from __future__ import annotations

import hashlib
from typing import Any

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.edges import stable_doc_id
from lfx_liam_bundle.graphrag.models import DocumentRecord, TextUnit
from lfx_liam_bundle.graphrag.tokens import count_tokens

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 100


def _unit_id(document_id: str, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{document_id}|{chunk_index}|{text[:64]}".encode()).hexdigest()[:12]  # noqa: S324
    return f"tu_{digest}"


def _encode(text: str) -> list[int] | list[str]:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return enc.encode(text)
    except Exception:  # noqa: BLE001
        # 无 tiktoken：按字符近似（CJK 友好）
        return list(text)


def _decode(tokens: list[int] | list[str]) -> str:
    if not tokens:
        return ""
    if isinstance(tokens[0], str):
        return "".join(tokens)  # type: ignore[arg-type]
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return enc.decode(tokens)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return "".join(str(t) for t in tokens)


def _split_by_tokens(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    tokens = _encode(text)
    if len(tokens) <= chunk_size:
        return [text]

    overlap = max(0, min(chunk_overlap, chunk_size // 2))
    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + chunk_size)
        piece = _decode(tokens[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(tokens):
            break
        start += step
        if len(chunks) > 10_000:
            break
    return chunks


def compose_text_units(
    documents: list[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    chunk_enabled: bool = True,
) -> tuple[list[TextUnit], list[DocumentRecord], dict[str, Any]]:
    """Documents → TextUnits + Document 表链接。"""
    size = max(64, int(chunk_size or DEFAULT_CHUNK_SIZE))
    overlap = max(0, int(chunk_overlap or 0))
    units: list[TextUnit] = []
    doc_records: dict[str, DocumentRecord] = {}

    for doc in documents:
        text = (doc.page_content or "").strip()
        if not text:
            continue
        meta = dict(doc.metadata or {})
        parent_doc_id = str(
            meta.get("document_id") or meta.get("source") or doc.id or stable_doc_id(text, meta)
        )
        doc_title = str(meta.get("title") or meta.get("filename") or meta.get("source") or parent_doc_id)
        pieces = _split_by_tokens(text, chunk_size=size, chunk_overlap=overlap) if chunk_enabled else [text]
        if not pieces:
            continue

        rec = doc_records.get(parent_doc_id)
        if rec is None:
            rec = DocumentRecord(
                id=parent_doc_id,
                title=doc_title,
                text=text[:2000],
                text_unit_ids=[],
                metadata=meta,
            )
            doc_records[parent_doc_id] = rec

        for i, piece in enumerate(pieces):
            uid = _unit_id(parent_doc_id, i, piece)
            umeta = dict(meta)
            umeta["doc_id"] = uid
            umeta["document_id"] = parent_doc_id
            umeta["chunk_index"] = i
            units.append(
                TextUnit(
                    id=uid,
                    text=piece,
                    metadata=umeta,
                    document_id=parent_doc_id,
                    n_tokens=count_tokens(piece),
                )
            )
            if uid not in rec.text_unit_ids:
                rec.text_unit_ids.append(uid)

    stats = {
        "documents": len(doc_records),
        "text_units": len(units),
        "chunk_enabled": chunk_enabled,
        "chunk_size": size,
        "chunk_overlap": overlap,
    }
    return units, list(doc_records.values()), stats

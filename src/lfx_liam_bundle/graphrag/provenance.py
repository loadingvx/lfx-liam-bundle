"""Entity ↔ TextUnit ↔ Document 双向溯源（对齐微软 GraphRAG provenance / breadcrumbs）。

论文与官方 data_model 要求：
- Entity.text_unit_ids：实体 → 原文片段
- TextUnit.entity_ids / relationship_ids / covariate_ids：原文 → 图元素
- Document.text_unit_ids 与 TextUnit.document_id：文档 ↔ 片段
Local Search 通过 Entity-TextUnit Mapping 把答案锚定到原文。
"""

from __future__ import annotations

from typing import Any

from lfx_liam_bundle.graphrag.models import GraphIndex, TextUnit


def _approx_tokens(text: str) -> int:
    """无 tiktoken 时的近似 token 数（中文偏字符、英文偏词）。"""
    raw = text or ""
    if not raw:
        return 0
    # 含大量 CJK 时按字符估；否则按空白分词
    cjk = sum(1 for ch in raw if "\u4e00" <= ch <= "\u9fff")
    if cjk >= max(1, len(raw) // 4):
        return max(1, len(raw))
    return max(1, len(raw.split()))


def link_provenance(index: GraphIndex) -> dict[str, Any]:
    """根据正向链接回填 TextUnit 反向索引，并校正 Document↔TextUnit。

    必须在抽取/合并完成后、持久化之前调用。
    """
    units_by_id = {u.id: u for u in index.text_units}
    docs_by_id = {d.id: d for d in index.documents}

    # 重置反向字段，避免追加合并后脏数据
    for u in index.text_units:
        u.entity_ids = []
        u.relationship_ids = []
        u.covariate_ids = []
        if u.n_tokens is None or u.n_tokens <= 0:
            u.n_tokens = _approx_tokens(u.text)

    # Entity → TextUnit（已有）同时回填 TextUnit.entity_ids
    for e in index.entities:
        clean_ids: list[str] = []
        for uid in e.text_unit_ids or []:
            unit = units_by_id.get(uid)
            if not unit:
                continue
            clean_ids.append(uid)
            if e.id not in unit.entity_ids:
                unit.entity_ids.append(e.id)
        e.text_unit_ids = clean_ids

    for r in index.relationships:
        clean_ids = []
        for uid in r.text_unit_ids or []:
            unit = units_by_id.get(uid)
            if not unit:
                continue
            clean_ids.append(uid)
            if r.id not in unit.relationship_ids:
                unit.relationship_ids.append(r.id)
        r.text_unit_ids = clean_ids

    for c in index.covariates:
        clean_ids = []
        for uid in c.text_unit_ids or []:
            unit = units_by_id.get(uid)
            if not unit:
                continue
            clean_ids.append(uid)
            if c.id not in unit.covariate_ids:
                unit.covariate_ids.append(c.id)
        c.text_unit_ids = clean_ids

    # Document ↔ TextUnit
    for d in index.documents:
        d.text_unit_ids = []
    for u in index.text_units:
        doc_id = u.document_id
        if not doc_id:
            continue
        doc = docs_by_id.get(doc_id)
        if doc is None:
            # 孤儿 TextUnit：补一个文档壳，保证反向可查
            from lfx_liam_bundle.graphrag.models import DocumentRecord

            doc = DocumentRecord(id=doc_id, title=doc_id, text=u.text[:200], text_unit_ids=[])
            index.documents.append(doc)
            docs_by_id[doc_id] = doc
        if u.id not in doc.text_unit_ids:
            doc.text_unit_ids.append(u.id)

    linked_entities = sum(1 for e in index.entities if e.text_unit_ids)
    linked_units = sum(1 for u in index.text_units if u.entity_ids)
    return {
        "entities_with_sources": linked_entities,
        "text_units_with_entities": linked_units,
        "documents": len(index.documents),
        "orphan_entities": sum(1 for e in index.entities if not e.text_unit_ids),
        "orphan_text_units": sum(1 for u in index.text_units if not u.entity_ids),
    }


def resolve_entity(index: GraphIndex, key: str):
    """按实体 id 或标题（忽略空白/大小写）解析实体。"""
    key = (key or "").strip()
    if not key:
        return None
    by_id = {e.id: e for e in index.entities}
    if key in by_id:
        return by_id[key]
    norm = "".join(key.split()).casefold()
    for e in index.entities:
        if "".join(e.title.split()).casefold() == norm:
            return e
    return None


def entity_to_sources(index: GraphIndex, entity_key: str) -> dict[str, Any]:
    """实体 → 原文片段 / 所属文档（正向溯源）。"""
    entity = resolve_entity(index, entity_key)
    if entity is None:
        msg = f"未找到实体「{entity_key}」。请使用实体名称或实体 ID。"
        raise ValueError(msg)
    units_by_id = {u.id: u for u in index.text_units}
    docs_by_id = {d.id: d for d in index.documents}
    sources: list[dict[str, Any]] = []
    for uid in entity.text_unit_ids:
        unit = units_by_id.get(uid)
        if not unit:
            continue
        doc = docs_by_id.get(unit.document_id or "")
        sources.append(
            {
                "text_unit_id": unit.id,
                "document_id": unit.document_id,
                "document_title": (doc.title if doc else None) or unit.document_id,
                "n_tokens": unit.n_tokens,
                "text": unit.text,
                "preview": (unit.text or "")[:240],
            }
        )
    rels = [
        {
            "id": r.id,
            "source": r.source,
            "target": r.target,
            "description": r.description,
            "text_unit_ids": list(r.text_unit_ids),
        }
        for r in index.relationships
        if "".join(r.source.split()).casefold() == "".join(entity.title.split()).casefold()
        or "".join(r.target.split()).casefold() == "".join(entity.title.split()).casefold()
        or any(uid in entity.text_unit_ids for uid in (r.text_unit_ids or []))
    ]
    return {
        "direction": "entity_to_text",
        "entity": {
            "id": entity.id,
            "title": entity.title,
            "type": entity.type,
            "description": entity.description,
            "text_unit_ids": list(entity.text_unit_ids),
            "community_ids": list(entity.community_ids),
        },
        "sources": sources,
        "source_count": len(sources),
        "relationships": rels[:40],
        "message": (
            f"实体「{entity.title}」对应 {len(sources)} 个原文片段。"
            if sources
            else f"实体「{entity.title}」没有关联原文片段（建图时未写入 text_unit_ids）。"
        ),
    }


def text_unit_to_graph(index: GraphIndex, text_unit_id: str) -> dict[str, Any]:
    """原文片段 → 实体/关系/声明（反向溯源）。"""
    uid = (text_unit_id or "").strip()
    unit = next((u for u in index.text_units if u.id == uid), None)
    if unit is None:
        msg = f"未找到文本单元「{text_unit_id}」。"
        raise ValueError(msg)

    ents_by_id = {e.id: e for e in index.entities}
    rels_by_id = {r.id: r for r in index.relationships}
    covs_by_id = {c.id: c for c in index.covariates}
    doc = next((d for d in index.documents if d.id == unit.document_id), None)

    entities = [
        {"id": e.id, "title": e.title, "type": e.type, "description": e.description}
        for eid in unit.entity_ids
        if (e := ents_by_id.get(eid))
    ]
    relationships = [
        {
            "id": r.id,
            "source": r.source,
            "target": r.target,
            "description": r.description,
        }
        for rid in unit.relationship_ids
        if (r := rels_by_id.get(rid))
    ]
    covariates = [
        {"id": c.id, "subject": c.subject, "status": c.status, "description": c.description}
        for cid in unit.covariate_ids
        if (c := covs_by_id.get(cid))
    ]
    return {
        "direction": "text_to_entity",
        "text_unit": {
            "id": unit.id,
            "document_id": unit.document_id,
            "document_title": (doc.title if doc else None) or unit.document_id,
            "n_tokens": unit.n_tokens,
            "text": unit.text,
            "entity_ids": list(unit.entity_ids),
            "relationship_ids": list(unit.relationship_ids),
            "covariate_ids": list(unit.covariate_ids),
        },
        "entities": entities,
        "relationships": relationships,
        "covariates": covariates,
        "message": (
            f"文本单元「{unit.id}」关联实体 {len(entities)} 个、关系 {len(relationships)} 条、"
            f"声明 {len(covariates)} 条。"
        ),
    }


def document_to_graph(index: GraphIndex, document_id: str) -> dict[str, Any]:
    """文档 → TextUnit → 聚合实体（文档级溯源）。"""
    did = (document_id or "").strip()
    doc = next((d for d in index.documents if d.id == did), None)
    if doc is None:
        # 也允许用 title 查
        norm = "".join(did.split()).casefold()
        doc = next(
            (d for d in index.documents if "".join((d.title or d.id).split()).casefold() == norm),
            None,
        )
    if doc is None:
        msg = f"未找到文档「{document_id}」。"
        raise ValueError(msg)

    units = [u for u in index.text_units if u.id in set(doc.text_unit_ids) or u.document_id == doc.id]
    entity_ids: list[str] = []
    for u in units:
        for eid in u.entity_ids:
            if eid not in entity_ids:
                entity_ids.append(eid)
    ents_by_id = {e.id: e for e in index.entities}
    entities = [
        {"id": e.id, "title": e.title, "type": e.type, "text_unit_ids": list(e.text_unit_ids)}
        for eid in entity_ids
        if (e := ents_by_id.get(eid))
    ]
    return {
        "direction": "document_to_graph",
        "document": {
            "id": doc.id,
            "title": doc.title or doc.id,
            "text_unit_ids": list(doc.text_unit_ids),
            "text_preview": (doc.text or "")[:300],
        },
        "text_units": [{"id": u.id, "preview": u.text[:160], "entity_ids": list(u.entity_ids)} for u in units],
        "entities": entities,
        "message": f"文档「{doc.title or doc.id}」含 {len(units)} 个文本单元、{len(entities)} 个实体。",
    }


def collect_local_search_citations(
    index: GraphIndex,
    entity_ids: list[str],
    text_unit_ids: list[str],
) -> list[dict[str, Any]]:
    """为 Local Search 答案生成可审计引用列表。"""
    units_by_id = {u.id: u for u in index.text_units}
    ents_by_id = {e.id: e for e in index.entities}
    docs_by_id = {d.id: d for d in index.documents}
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for uid in text_unit_ids:
        unit = units_by_id.get(uid)
        if not unit or uid in seen:
            continue
        seen.add(uid)
        supporting = [ents_by_id[eid].title for eid in unit.entity_ids if eid in ents_by_id and eid in set(entity_ids)]
        doc = docs_by_id.get(unit.document_id or "")
        citations.append(
            {
                "text_unit_id": unit.id,
                "document_id": unit.document_id,
                "document_title": (doc.title if doc else None) or unit.document_id,
                "supports_entities": supporting,
                "preview": (unit.text or "")[:280],
            }
        )
    return citations


def format_sources_block(units: list[TextUnit], index: GraphIndex) -> str:
    docs_by_id = {d.id: d for d in index.documents}
    lines: list[str] = []
    for u in units:
        doc = docs_by_id.get(u.document_id or "")
        title = (doc.title if doc else None) or u.document_id or "未知文档"
        ent_titles = []
        ents_by_id = {e.id: e for e in index.entities}
        for eid in u.entity_ids[:8]:
            if eid in ents_by_id:
                ent_titles.append(ents_by_id[eid].title)
        ent_part = f"；关联实体: {', '.join(ent_titles)}" if ent_titles else ""
        lines.append(f"[{u.id}] 文档={title}{ent_part}\n{u.text}")
    return "\n\n".join(lines)

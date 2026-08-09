"""实体/关系抽取 + Data Gleaning + 合并消歧 + 描述摘要。

对齐微软 GraphRAG Phase 3：extract → glean → merge → summarize。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from lfx_liam_bundle.graphrag.llm_utils import invoke_llm, parse_json_payload
from lfx_liam_bundle.graphrag.models import Entity, Relationship, TextUnit

DEFAULT_ENTITY_TYPES = [
    "Organization",
    "Person",
    "Location",
    "Event",
    "Concept",
    "Product",
    "Technology",
]

EXTRACT_PROMPT = """You are a knowledge-graph extraction assistant. Extract entities and relationships from the text.
Allowed entity types: {entity_types}

Return strict JSON only (no Markdown):
{{
  "entities": [{{"title": "name", "type": "type", "description": "one-sentence description"}}],
  "relationships": [{{"source": "source name", "target": "target name", "description": "relationship", "weight": 1.0}}]
}}

Text:
{text}
"""

GLEAN_PROMPT = """You already extracted entities and relationships from the text. Perform Data Gleaning: add any missed entities/relationships.
Do not repeat existing items; if nothing new is found, return empty arrays.

Already extracted entities: {entities}
Already extracted relationships: {relationships}

Return strict JSON only:
{{
  "entities": [{{"title": "name", "type": "type", "description": "one-sentence description"}}],
  "relationships": [{{"source": "source name", "target": "target name", "description": "relationship", "weight": 1.0}}]
}}

Source text:
{text}
"""

SUMMARIZE_PROMPT = """Merge the following descriptions of the same entity/relationship into one concise description (max ~80 words). Output the description text only:
{descriptions}
"""


def _norm_title(title: str) -> str:
    t = re.sub(r"\s+", "", (title or "").strip())
    return t.casefold()


def _entity_id(title: str, etype: str) -> str:
    key = f"{_norm_title(title)}|{etype.strip().casefold()}"
    return "ent_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _rel_id(source: str, target: str) -> str:
    a, b = sorted([_norm_title(source), _norm_title(target)])
    key = f"{a}->{b}"
    return "rel_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _parse_extraction(payload: Any) -> tuple[list[dict], list[dict]]:
    if not isinstance(payload, dict):
        return [], []
    ents = payload.get("entities") or []
    rels = payload.get("relationships") or []
    if not isinstance(ents, list):
        ents = []
    if not isinstance(rels, list):
        rels = []
    return ents, rels


def extract_from_text_unit(
    llm: Any,
    unit: TextUnit,
    *,
    entity_types: list[str] | None = None,
    max_gleanings: int = 1,
) -> tuple[list[dict], list[dict]]:
    types = entity_types or DEFAULT_ENTITY_TYPES
    prompt = EXTRACT_PROMPT.format(entity_types="、".join(types), text=unit.text[:6000])
    try:
        payload = parse_json_payload(invoke_llm(llm, prompt))
    except Exception:
        return [], []
    entities, relationships = _parse_extraction(payload)

    for _ in range(max(0, int(max_gleanings))):
        glean_prompt = GLEAN_PROMPT.format(
            entities=[e.get("title") for e in entities][:80],
            relationships=[f"{r.get('source')}->{r.get('target')}" for r in relationships][:80],
            text=unit.text[:6000],
        )
        try:
            glean = parse_json_payload(invoke_llm(llm, glean_prompt))
        except Exception:
            break
        g_ents, g_rels = _parse_extraction(glean)
        if not g_ents and not g_rels:
            break
        entities.extend(g_ents)
        relationships.extend(g_rels)
    return entities, relationships


def merge_graph_primitives(
    extractions: list[tuple[str, list[dict], list[dict]]],
    llm: Any | None = None,
) -> tuple[list[Entity], list[Relationship]]:
    """按 title+type / source+target 合并，并用 LLM 摘要多描述。"""
    ent_bucket: dict[str, dict[str, Any]] = {}
    rel_bucket: dict[str, dict[str, Any]] = {}

    for unit_id, ents, rels in extractions:
        for e in ents:
            title = str(e.get("title") or "").strip()
            if not title:
                continue
            etype = str(e.get("type") or "UNKNOWN").strip() or "UNKNOWN"
            eid = _entity_id(title, etype)
            slot = ent_bucket.setdefault(
                eid,
                {
                    "id": eid,
                    "title": title,
                    "type": etype,
                    "descriptions": [],
                    "text_unit_ids": [],
                },
            )
            desc = str(e.get("description") or "").strip()
            if desc:
                slot["descriptions"].append(desc)
            if unit_id not in slot["text_unit_ids"]:
                slot["text_unit_ids"].append(unit_id)

        for r in rels:
            source = str(r.get("source") or "").strip()
            target = str(r.get("target") or "").strip()
            if not source or not target:
                continue
            rid = _rel_id(source, target)
            slot = rel_bucket.setdefault(
                rid,
                {
                    "id": rid,
                    "source": source,
                    "target": target,
                    "descriptions": [],
                    "weight": 0.0,
                    "text_unit_ids": [],
                },
            )
            desc = str(r.get("description") or "").strip()
            if desc:
                slot["descriptions"].append(desc)
            try:
                slot["weight"] += float(r.get("weight") or 1.0)
            except (TypeError, ValueError):
                slot["weight"] += 1.0
            if unit_id not in slot["text_unit_ids"]:
                slot["text_unit_ids"].append(unit_id)

    entities: list[Entity] = []
    for slot in ent_bucket.values():
        descriptions = slot["descriptions"] or [slot["title"]]
        if llm is not None and len(descriptions) > 1:
            try:
                summary = invoke_llm(
                    llm,
                    SUMMARIZE_PROMPT.format(
                        descriptions="\n".join(f"- {d}" for d in descriptions[:12])
                    ),
                )
                description = summary.strip() or "；".join(descriptions[:3])
            except Exception:
                description = "；".join(descriptions[:3])
        else:
            description = "；".join(descriptions[:3])
        entities.append(
            Entity(
                id=slot["id"],
                title=slot["title"],
                type=slot["type"],
                description=description,
                text_unit_ids=slot["text_unit_ids"],
                rank=float(len(slot["text_unit_ids"])),
            )
        )

    # map titles to canonical entity titles for relationships
    title_map = {_norm_title(e.title): e.title for e in entities}
    relationships: list[Relationship] = []
    for slot in rel_bucket.values():
        source = title_map.get(_norm_title(slot["source"]), slot["source"])
        target = title_map.get(_norm_title(slot["target"]), slot["target"])
        descriptions = slot["descriptions"] or [f"{source} 与 {target} 相关"]
        if llm is not None and len(descriptions) > 1:
            try:
                summary = invoke_llm(
                    llm,
                    SUMMARIZE_PROMPT.format(
                        descriptions="\n".join(f"- {d}" for d in descriptions[:12])
                    ),
                )
                description = summary.strip() or "；".join(descriptions[:3])
            except Exception:
                description = "；".join(descriptions[:3])
        else:
            description = "；".join(descriptions[:3])
        relationships.append(
            Relationship(
                id=slot["id"],
                source=source,
                target=target,
                description=description,
                weight=float(slot["weight"] or 1.0),
                text_unit_ids=slot["text_unit_ids"],
            )
        )
    return entities, relationships


def extract_graph_from_units(
    llm: Any,
    units: list[TextUnit],
    *,
    entity_types: list[str] | None = None,
    max_gleanings: int = 1,
) -> tuple[list[Entity], list[Relationship], dict[str, Any]]:
    if llm is None:
        msg = "完整 GraphRAG 建图需要 LLM 进行实体/关系抽取与 Gleaning。"
        raise ValueError(msg)
    if not units:
        msg = "没有 TextUnit 可供抽取。"
        raise ValueError(msg)

    extractions: list[tuple[str, list[dict], list[dict]]] = []
    failed = 0
    for unit in units:
        ents, rels = extract_from_text_unit(
            llm, unit, entity_types=entity_types, max_gleanings=max_gleanings
        )
        if not ents and not rels:
            failed += 1
        extractions.append((unit.id, ents, rels))

    entities, relationships = merge_graph_primitives(extractions, llm=llm)
    # 规范化关系端点为规范实体名
    title_map = {_norm_title(e.title): e.title for e in entities}
    for r in relationships:
        r.source = title_map.get(_norm_title(r.source), r.source)
        r.target = title_map.get(_norm_title(r.target), r.target)

    stats = {
        "units": len(units),
        "units_failed_extraction": failed,
        "entities": len(entities),
        "relationships": len(relationships),
        "max_gleanings": max_gleanings,
        "gleaning_enabled": max_gleanings > 0,
    }
    if not entities:
        msg = (
            "未能抽取到任何实体。请检查 LLM 是否可用、文本是否有信息量，"
            "或提高「Gleaning 轮数」/ 调整实体类型后重试。"
        )
        raise ValueError(msg)
    return entities, relationships, stats

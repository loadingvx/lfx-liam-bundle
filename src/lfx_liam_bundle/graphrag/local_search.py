"""Local Search：实体语义入口 → 邻域 + Entity-TextUnit Mapping 原文溯源。"""

from __future__ import annotations

import math
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.llm_utils import invoke_llm
from lfx_liam_bundle.graphrag.models import GraphIndex
from lfx_liam_bundle.graphrag.provenance import collect_local_search_citations, format_sources_block
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

LOCAL_ANSWER_PROMPT = """你是 GraphRAG Local Search 助手。请仅依据给定上下文回答用户问题。
回答中凡引用事实，必须标注来源文本单元 ID，格式如 [tu_xxx]（使用上下文里「原文片段」的方括号 ID）。
若上下文不足，明确说明知识库中未找到足够信息，不要编造。

问题：{query}

上下文：
{context}
"""


def _norm(title: str) -> str:
    return "".join((title or "").split()).casefold()


def _cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


def build_local_context(
    index: GraphIndex,
    query: str,
    embedding: Embeddings,
    *,
    top_k_entities: int = 8,
    top_k_relationships: int = 12,
    top_k_chunks: int = 6,
    community_prop: float = 0.3,
    text_unit_prop: float = 0.5,
) -> tuple[str, list[Document], dict[str, Any]]:
    if not index.entities:
        msg = (
            "知识库中没有实体，无法 Local Search。"
            "请先用完整 GraphRAG「入库建图」完成索引。"
        )
        raise ValueError(msg)

    qvec = embedding.embed_query(query)
    missing = [e for e in index.entities if not e.description_embedding]
    if missing:
        vectors = embedding.embed_documents([f"{e.title}: {e.description}" for e in missing])
        for e, vec in zip(missing, vectors, strict=True):
            e.description_embedding = vec

    ranked_entities = sorted(
        index.entities,
        key=lambda e: (_cosine(qvec, e.description_embedding), e.rank),
        reverse=True,
    )[:top_k_entities]
    if not ranked_entities:
        msg = "未能匹配到相关实体。请换个问法，或确认建图内容是否覆盖该主题。"
        raise ValueError(msg)

    seed_titles = {_norm(e.title) for e in ranked_entities}
    seed_ids = {e.id for e in ranked_entities}

    rels = [
        r
        for r in index.relationships
        if _norm(r.source) in seed_titles or _norm(r.target) in seed_titles
    ]
    rels = sorted(rels, key=lambda r: (r.weight, r.rank), reverse=True)[:top_k_relationships]

    neighbor_titles = {_norm(r.source) for r in rels} | {_norm(r.target) for r in rels}
    neighbors = [
        e for e in index.entities if _norm(e.title) in neighbor_titles and e.id not in seed_ids
    ]
    neighbors = sorted(neighbors, key=lambda e: e.rank, reverse=True)[:top_k_entities]

    community_ids: list[str] = []
    for e in ranked_entities:
        community_ids.extend(e.community_ids)
    community_ids = list(dict.fromkeys(community_ids))
    reports = [r for r in index.community_reports if r.community_id in community_ids]
    reports = sorted(reports, key=lambda r: r.rank, reverse=True)

    # Entity-TextUnit Mapping（微软 Local Search 核心）
    unit_ids: list[str] = []
    for e in ranked_entities:
        unit_ids.extend(e.text_unit_ids)
    for r in rels:
        unit_ids.extend(r.text_unit_ids or [])
    unit_ids = list(dict.fromkeys(unit_ids))
    units = [u for u in index.text_units if u.id in unit_ids]
    missing_u = [u for u in units if not u.embedding]
    if missing_u:
        vectors = embedding.embed_documents([u.text for u in missing_u])
        for u, vec in zip(missing_u, vectors, strict=True):
            u.embedding = vec
    # text_unit_prop 控制原文占比（与 community_prop 配合）
    chunk_budget = max(1, int(top_k_chunks * max(0.2, min(text_unit_prop * 2, 1.5))))
    scored_units = sorted(units, key=lambda u: _cosine(qvec, u.embedding), reverse=True)[:chunk_budget]
    if not scored_units:
        scored_units = units[:chunk_budget]

    claims = [
        c
        for c in index.covariates
        if _norm(c.subject) in seed_titles
        or any(_norm(c.subject) == _norm(e.title) for e in ranked_entities)
    ][:12]

    sections: list[str] = []
    sections.append(
        "## 相关实体\n"
        + "\n".join(
            f"- {e.title} ({e.type}, rank={e.rank:.1f}, sources={len(e.text_unit_ids)}): {e.description}"
            for e in ranked_entities
        )
    )
    if neighbors:
        sections.append(
            "## 关联实体\n" + "\n".join(f"- {e.title} ({e.type}): {e.description}" for e in neighbors)
        )
    if rels:
        sections.append(
            "## 关系\n"
            + "\n".join(
                f"- {r.source} -> {r.target}: {r.description} (来源片段:{','.join((r.text_unit_ids or [])[:3]) or '无'})"
                for r in rels
            )
        )
    if claims:
        sections.append(
            "## 事实声明\n"
            + "\n".join(
                f"- [{c.status}] {c.subject}: {c.description} (来源:{','.join((c.text_unit_ids or [])[:3]) or '无'})"
                for c in claims
            )
        )
    max_reports = max(1, int(max(1, len(reports)) * max(0.1, min(community_prop * 3, 1.0)))) if reports else 0
    if reports:
        sections.append(
            "## 社区报告\n"
            + "\n\n".join(f"### {r.title}\n{r.summary}\n{r.full_content}" for r in reports[:max_reports])
        )
    if scored_units:
        sections.append("## 原文片段（请在答案中引用方括号 ID）\n" + format_sources_block(scored_units, index))

    citations = collect_local_search_citations(
        index,
        entity_ids=[e.id for e in ranked_entities],
        text_unit_ids=[u.id for u in scored_units],
    )

    context = "\n\n".join(sections)
    docs = [
        Document(
            page_content=e.description,
            metadata={
                "kind": "entity",
                "title": e.title,
                "type": e.type,
                "id": e.id,
                "rank": e.rank,
                "text_unit_ids": list(e.text_unit_ids),
            },
            id=e.id,
        )
        for e in ranked_entities
    ]
    docs.extend(
        Document(
            page_content=u.text,
            metadata={
                "kind": "text_unit",
                "id": u.id,
                "document_id": u.document_id,
                "entity_ids": list(u.entity_ids),
            },
            id=u.id,
        )
        for u in scored_units
    )
    meta = {
        "mode": "local_search",
        "entities": len(ranked_entities),
        "relationships": len(rels),
        "reports": min(len(reports), max_reports) if reports else 0,
        "text_units": len(scored_units),
        "claims": len(claims),
        "citations": citations,
        "provenance": {
            "entity_text_unit_mapping": True,
            "cited_text_units": [c["text_unit_id"] for c in citations],
            "cited_documents": list(
                dict.fromkeys(c["document_id"] for c in citations if c.get("document_id"))
            ),
        },
    }
    return context, docs, meta


def local_search(
    kb: GraphRAGKnowledgeBase,
    query: str,
    embedding: Embeddings,
    *,
    llm: Any | None = None,
    top_k_entities: int = 8,
    top_k_chunks: int = 6,
    answer_with_llm: bool = True,
) -> tuple[list[Document], str, dict[str, Any]]:
    index = load_index(kb)
    context, docs, meta = build_local_context(
        index,
        query,
        embedding,
        top_k_entities=top_k_entities,
        top_k_chunks=top_k_chunks,
    )
    if answer_with_llm and llm is not None:
        answer = invoke_llm(llm, LOCAL_ANSWER_PROMPT.format(query=query, context=context[:12000]))
        # 附上可审计引用，避免模型漏标时用户仍能核对
        if meta.get("citations"):
            cite_lines = "\n".join(
                f"- [{c['text_unit_id']}] {c.get('document_title') or c.get('document_id')}: {c['preview'][:120]}"
                for c in meta["citations"]
            )
            answer = f"{answer.strip()}\n\n---\n【可核对原文出处】\n{cite_lines}"
        meta["answer"] = answer
        return docs, answer, meta
    if answer_with_llm and llm is None:
        meta["warning"] = "未连接 LLM，已返回检索上下文（未生成最终答案）。"
    return docs, context, meta

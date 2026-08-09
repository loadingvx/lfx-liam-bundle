"""Local Search：实体入口 + 邻域 + Entity-TextUnit Mapping，严格 token 预算。"""

from __future__ import annotations

import math
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.kg_store import load_index, load_subgraph
from lfx_liam_bundle.graphrag.llm_utils import invoke_llm
from lfx_liam_bundle.graphrag.models import GraphIndex
from lfx_liam_bundle.graphrag.provenance import collect_local_search_citations
from lfx_liam_bundle.graphrag.tokens import allocate_budget, join_under_budget
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

LOCAL_ANSWER_PROMPT = """你是 GraphRAG Local Search 助手。请仅依据给定上下文回答用户问题。
回答中凡引用事实，必须标注来源文本单元 ID，格式如 [tu_xxx]。
若上下文不足，明确说明知识库中未找到足够信息，不要编造。
期望回答形式：{response_type}

{history_block}问题：{query}

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


def _history_block(history: str | None) -> str:
    h = (history or "").strip()
    if not h:
        return ""
    return f"对话历史：\n{h}\n\n"


def build_local_context(
    index: GraphIndex,
    query: str,
    embedding: Embeddings,
    *,
    top_k_entities: int = 8,
    top_k_relationships: int = 12,
    top_k_chunks: int = 6,
    community_prop: float = 0.25,
    text_unit_prop: float = 0.5,
    max_context_tokens: int = 8000,
    seed_entity_ids: list[str] | None = None,
    ranking_source: str = "exact_cosine",
    query_vector: list[float] | None = None,
) -> tuple[str, list[Document], dict[str, Any]]:
    if not index.entities:
        msg = "知识库中没有实体，无法 Local Search。请先完成入库建图。"
        raise ValueError(msg)

    budget = allocate_budget(
        max_context_tokens, text_unit_prop=text_unit_prop, community_prop=community_prop
    )
    qvec = query_vector if query_vector is not None else embedding.embed_query(query)
    missing = [e for e in index.entities if not e.description_embedding]
    if missing:
        vectors = embedding.embed_documents([f"{e.title}: {e.description}" for e in missing])
        for e, vec in zip(missing, vectors, strict=True):
            e.description_embedding = vec

    ranked_entities: list = []
    if seed_entity_ids:
        by_id = {e.id: e for e in index.entities}
        ranked_entities = [by_id[i] for i in seed_entity_ids if i in by_id]
    if not ranked_entities:
        ranked_entities = sorted(
            index.entities,
            key=lambda e: (_cosine(qvec, e.description_embedding), e.rank),
            reverse=True,
        )[:top_k_entities]
        ranking_source = "exact_cosine" if seed_entity_ids else ranking_source
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
    reports = sorted(
        [r for r in index.community_reports if r.community_id in community_ids],
        key=lambda r: r.rank,
        reverse=True,
    )

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
    scored_units = sorted(units, key=lambda u: _cosine(qvec, u.embedding), reverse=True)[:top_k_chunks]

    claims = [
        c
        for c in index.covariates
        if _norm(c.subject) in seed_titles
    ][:12]

    # graph 段预算
    graph_items = [
        "相关实体\n"
        + "\n".join(
            f"- {e.title} ({e.type}, rank={e.rank:.1f}): {e.description}" for e in ranked_entities
        )
    ]
    if neighbors:
        graph_items.append(
            "关联实体\n" + "\n".join(f"- {e.title} ({e.type}): {e.description}" for e in neighbors)
        )
    if rels:
        graph_items.append(
            "关系\n"
            + "\n".join(f"- {r.source} -> {r.target}: {r.description}" for r in rels)
        )
    if claims:
        graph_items.append(
            "事实声明\n"
            + "\n".join(
                f"- [{c.status}] {c.subject}: {c.description}"
                + (f" ({c.start_date}~{c.end_date})" if c.start_date or c.end_date else "")
                for c in claims
            )
        )
    graph_block = join_under_budget(graph_items, max_tokens=budget["graph"], sep="\n\n")

    report_items = [f"### {r.title}\n{r.summary}\n{r.full_content}" for r in reports]
    report_block = join_under_budget(report_items, max_tokens=budget["community_reports"], sep="\n\n")

    docs_by_id = {d.id: d for d in index.documents}
    ents_by_id = {e.id: e for e in index.entities}
    unit_items: list[str] = []
    for u in scored_units:
        doc = docs_by_id.get(u.document_id or "")
        title = (doc.title if doc else None) or u.document_id or "未知文档"
        ent_titles = [ents_by_id[eid].title for eid in u.entity_ids[:6] if eid in ents_by_id]
        ent_part = f"；关联实体: {', '.join(ent_titles)}" if ent_titles else ""
        unit_items.append(f"[{u.id}] 文档={title}{ent_part}\n{u.text}")
    unit_block = join_under_budget(unit_items, max_tokens=budget["text_units"], sep="\n\n")

    sections = [graph_block]
    if report_block:
        sections.append("## 社区报告\n" + report_block)
    if unit_block:
        sections.append("## 原文片段（请在答案中引用方括号 ID）\n" + unit_block)
    context = "\n\n".join(s for s in sections if s)

    citations = collect_local_search_citations(
        index,
        entity_ids=[e.id for e in ranked_entities],
        text_unit_ids=[u.id for u in scored_units],
    )
    docs = [
        Document(
            page_content=e.description,
            metadata={
                "kind": "entity",
                "title": e.title,
                "type": e.type,
                "id": e.id,
                "text_unit_ids": list(e.text_unit_ids),
            },
            id=e.id,
        )
        for e in ranked_entities
    ]
    docs.extend(
        Document(
            page_content=u.text,
            metadata={"kind": "text_unit", "id": u.id, "document_id": u.document_id},
            id=u.id,
        )
        for u in scored_units
    )
    meta = {
        "mode": "local_search",
        "entities": len(ranked_entities),
        "relationships": len(rels),
        "reports": len(reports),
        "text_units": len(scored_units),
        "claims": len(claims),
        "token_budget": budget,
        "vector_ranking": ranking_source,
        "citations": citations,
        "provenance": {
            "entity_text_unit_mapping": True,
            "cited_text_units": [c["text_unit_id"] for c in citations],
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
    max_context_tokens: int = 8000,
    text_unit_prop: float = 0.5,
    community_prop: float = 0.25,
    conversation_history: str | None = None,
    response_type: str = "多段落中文回答",
) -> tuple[list[Document], str, dict[str, Any]]:
    from lfx_liam_bundle.graphrag.vector_search import ann_search_entities

    qvec = embedding.embed_query(query)
    seed_ids: list[str] | None = None
    ranking_source = "exact_cosine"
    ann_warning: str | None = None

    if kb.use_vector_index:
        try:
            hits = ann_search_entities(kb, qvec, top_k=top_k_entities)
            if hits:
                seed_ids = [doc_id for doc_id, _ in hits]
                ranking_source = f"ann:{kb.backend}"
            else:
                ann_warning = "向量检索未返回实体，已回退精确余弦。"
                ranking_source = "exact_cosine_fallback"
        except Exception as e:
            if not kb.ann_fallback_exact:
                raise
            ann_warning = f"向量检索不可用，已回退精确余弦：{e}"
            ranking_source = "exact_cosine_fallback"

    if seed_ids:
        index = load_subgraph(kb, entity_ids=seed_ids, include_neighbors=True)
        load_mode = "subgraph"
    else:
        index = load_index(kb)
        load_mode = "full"
    context, docs, meta = build_local_context(
        index,
        query,
        embedding,
        top_k_entities=top_k_entities,
        top_k_chunks=top_k_chunks,
        max_context_tokens=max_context_tokens,
        text_unit_prop=text_unit_prop,
        community_prop=community_prop,
        seed_entity_ids=seed_ids,
        ranking_source=ranking_source,
        query_vector=qvec,
    )
    meta["index_load"] = load_mode
    if ann_warning:
        meta["vector_ann_warning"] = ann_warning
    if answer_with_llm and llm is not None:
        answer = invoke_llm(
            llm,
            LOCAL_ANSWER_PROMPT.format(
                query=query,
                context=context,
                response_type=response_type or "多段落中文回答",
                history_block=_history_block(conversation_history),
            ),
        )
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

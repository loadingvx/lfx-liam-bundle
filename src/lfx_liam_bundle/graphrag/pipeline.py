"""完整 GraphRAG 索引流水线（对齐微软默认 dataflow Phase 1/3/4/5/6）。

流程：
Documents → TextUnits → Extract(+Gleaning) → Summarize → Claims(可选)
→ Hierarchical Communities → Community Reports → Embeddings → Persist
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.claims import extract_claims_from_units
from lfx_liam_bundle.graphrag.communities import detect_hierarchical_communities
from lfx_liam_bundle.graphrag.community_reports import generate_community_reports
from lfx_liam_bundle.graphrag.edges import coerce_documents, stable_doc_id
from lfx_liam_bundle.graphrag.extract_graph import DEFAULT_ENTITY_TYPES, extract_graph_from_units
from lfx_liam_bundle.graphrag.kg_store import load_index, persist_index
from lfx_liam_bundle.graphrag.models import (
    Community,
    DocumentRecord,
    GraphIndex,
    TextUnit,
    merge_graph_indexes,
)
from lfx_liam_bundle.graphrag.provenance import link_provenance
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def documents_to_text_units(
    documents: list[Document],
) -> tuple[list[TextUnit], list[DocumentRecord]]:
    units: list[TextUnit] = []
    doc_records: dict[str, DocumentRecord] = {}
    for doc in documents:
        text = (doc.page_content or "").strip()
        if not text:
            continue
        meta = dict(doc.metadata or {})
        uid = str(doc.id or meta.get("doc_id") or stable_doc_id(text, meta))
        parent_doc_id = str(meta.get("document_id") or meta.get("source") or uid)
        doc_title = str(meta.get("title") or meta.get("filename") or meta.get("source") or parent_doc_id)
        meta["doc_id"] = uid
        units.append(
            TextUnit(
                id=uid,
                text=text,
                metadata=meta,
                document_id=parent_doc_id,
                n_tokens=max(1, len(text) if any("\u4e00" <= ch <= "\u9fff" for ch in text) else len(text.split())),
            )
        )
        rec = doc_records.get(parent_doc_id)
        if rec is None:
            rec = DocumentRecord(
                id=parent_doc_id,
                title=doc_title,
                text=text[:500],
                text_unit_ids=[],
                metadata=meta,
            )
            doc_records[parent_doc_id] = rec
        if uid not in rec.text_unit_ids:
            rec.text_unit_ids.append(uid)
    return units, list(doc_records.values())


def run_indexing_pipeline(
    kb: GraphRAGKnowledgeBase,
    ingest_data: Any,
    *,
    llm: Any,
    embedding: Embeddings | None,
    max_gleanings: int = 1,
    max_cluster_size: int = 10,
    max_community_levels: int = 3,
    entity_types: list[str] | None = None,
    replace: bool = True,
    extract_claims: bool = False,
) -> tuple[GraphRAGKnowledgeBase, GraphIndex, dict[str, Any]]:
    """执行完整 Microsoft-compatible GraphRAG 索引。"""
    if llm is None:
        msg = (
            "完整 GraphRAG 建图需要连接 LLM（实体/关系抽取、Data Gleaning、社区报告）。"
            "请在「入库建图」组件连接语言模型。"
        )
        raise ValueError(msg)
    if embedding is None:
        msg = (
            "完整 GraphRAG 需要 Embedding 模型"
            "（TextUnit / 实体描述 / 社区报告向量化，供 Local Search 使用）。"
        )
        raise ValueError(msg)

    documents = coerce_documents(ingest_data)
    units, doc_records = documents_to_text_units(documents)
    if not units:
        msg = "没有可索引的文本单元。请检查上游文档是否包含有效文本（不能全为空）。"
        raise ValueError(msg)

    entities, relationships, extract_stats = extract_graph_from_units(
        llm,
        units,
        entity_types=entity_types or DEFAULT_ENTITY_TYPES,
        max_gleanings=max_gleanings,
    )

    covariates = []
    if extract_claims:
        covariates = extract_claims_from_units(llm, units)
        extract_stats["covariates"] = len(covariates)

    incoming = GraphIndex(
        text_units=units,
        entities=entities,
        relationships=relationships,
        covariates=covariates,
        documents=doc_records,
    )

    if not replace:
        try:
            existing = load_index(kb)
            if existing.entities or existing.text_units:
                incoming = merge_graph_indexes(existing, incoming)
                extract_stats["merged_with_existing"] = True
        except Exception:
            extract_stats["merged_with_existing"] = False

    communities = detect_hierarchical_communities(
        incoming.entities,
        incoming.relationships,
        max_cluster_size=max_cluster_size,
        max_levels=max_community_levels,
    )
    if not communities:
        communities = [
            Community(
                id="comm_L0_0",
                level=0,
                parent=None,
                entity_ids=[e.id for e in incoming.entities],
                title="全域社区",
            )
        ]
        for e in incoming.entities:
            e.community_ids = ["comm_L0_0"]

    reports = generate_community_reports(
        llm,
        communities,
        incoming.entities,
        incoming.relationships,
        covariates=incoming.covariates,
    )
    index = GraphIndex(
        text_units=incoming.text_units,
        entities=incoming.entities,
        relationships=incoming.relationships,
        communities=communities,
        community_reports=reports,
        covariates=incoming.covariates,
        documents=incoming.documents,
    )
    # 双向溯源：Entity↔TextUnit↔Document（论文 provenance / breadcrumbs）
    provenance_stats = link_provenance(index)
    # 追加模式也整库重写社区/报告（图结构已合并），保证一致性
    persist_stats = persist_index(kb, index, embedding, replace=True)

    kb.document_count = len(index.text_units)
    kb.status = "ready"
    orphan_e = provenance_stats.get("orphan_entities", 0)
    kb.message = (
        f"GraphRAG 索引完成：文本单元 {len(index.text_units)}，实体 {len(index.entities)}，"
        f"关系 {len(index.relationships)}，社区 {len(communities)}，报告 {len(reports)}"
        + (f"，声明 {len(index.covariates)}" if index.covariates else "")
        + f"；溯源已链接（有原文的实体 {provenance_stats.get('entities_with_sources', 0)}/"
        f"{len(index.entities)}）。"
    )
    if orphan_e:
        kb.message += f" 注意：{orphan_e} 个实体缺少原文链接。"
    summary = {
        "message": kb.message,
        "extract": extract_stats,
        "index": index.stats(),
        "provenance": provenance_stats,
        "persist": persist_stats,
        "pipeline": "microsoft_graphrag_compatible_v1",
        "phases": [
            "compose_text_units",
            "link_documents_text_units",
            "extract_entities_relationships_gleaning",
            "summarize_descriptions",
            "claim_extraction" if extract_claims else "claim_extraction_skipped",
            "hierarchical_community_detection",
            "community_reports",
            "link_provenance_bidirectional",
            "text_embeddings",
            "persist_knowledge_model",
        ],
    }
    return kb, index, summary

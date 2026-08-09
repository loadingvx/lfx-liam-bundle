"""完整 GraphRAG 索引流水线（标准 / FastGraphRAG）。"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, compose_text_units
from lfx_liam_bundle.graphrag.claims import extract_claims_from_units
from lfx_liam_bundle.graphrag.communities import detect_hierarchical_communities
from lfx_liam_bundle.graphrag.community_reports import generate_community_reports
from lfx_liam_bundle.graphrag.edges import coerce_documents
from lfx_liam_bundle.graphrag.extract_graph import DEFAULT_ENTITY_TYPES, extract_graph_from_units
from lfx_liam_bundle.graphrag.fast_extract import extract_graph_fast
from lfx_liam_bundle.graphrag.kg_store import load_index, persist_index
from lfx_liam_bundle.graphrag.models import Community, GraphIndex, merge_graph_indexes
from lfx_liam_bundle.graphrag.provenance import link_provenance
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

IndexingMethod = Literal["standard", "fast"]


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
    chunk_enabled: bool = True,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    indexing_method: IndexingMethod | str = "standard",
) -> tuple[GraphRAGKnowledgeBase, GraphIndex, dict[str, Any]]:
    method = (indexing_method or "standard").strip().lower()
    if method in {"fast", "fastgraphrag", "fast_graphrag", "快速", "快速建图"}:
        method = "fast"
    else:
        method = "standard"

    if llm is None:
        msg = (
            "建图需要连接 LLM。"
            "标准模式：实体/关系抽取、Gleaning、社区报告；"
            "FastGraphRAG：实体由 NLP 抽取，但仍需 LLM 生成社区报告。"
        )
        raise ValueError(msg)
    if embedding is None:
        msg = "建图需要 Embedding 模型（TextUnit / 实体描述 / 社区报告向量化）。"
        raise ValueError(msg)

    documents = coerce_documents(ingest_data)
    units, doc_records, chunk_stats = compose_text_units(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_enabled=chunk_enabled,
    )
    if not units:
        msg = "没有可索引的文本单元。请检查上游文档是否包含有效文本。"
        raise ValueError(msg)

    if method == "fast":
        entities, relationships, extract_stats = extract_graph_fast(units)
        covariates: list = []
        extract_stats["claims"] = 0
        extract_phases = [
            "compose_text_units_token_chunking",
            "link_documents_text_units",
            "fast_nlp_entity_cooccurrence",
            "claim_extraction_skipped",
        ]
    else:
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
        extract_phases = [
            "compose_text_units_token_chunking",
            "link_documents_text_units",
            "extract_entities_relationships_gleaning",
            "summarize_descriptions",
            "claim_extraction" if extract_claims else "claim_extraction_skipped",
        ]

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

    communities, community_stats = detect_hierarchical_communities(
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
        community_stats = {"algorithm": "singleton_fallback", "communities": 1}

    reports = generate_community_reports(
        llm,
        communities,
        incoming.entities,
        incoming.relationships,
        covariates=incoming.covariates,
        text_units=incoming.text_units if method == "fast" else None,
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
    provenance_stats = link_provenance(index)
    persist_stats = persist_index(kb, index, embedding, replace=True)

    kb.document_count = len(index.text_units)
    kb.status = "ready"
    ann_state = persist_stats.get("vector_ann", "disabled")
    ann_note = {
        "ready": "向量ANN=就绪",
        "failed": "向量ANN=失败(将回退精确余弦)",
        "disabled": "向量ANN=关闭",
    }.get(str(ann_state), f"向量ANN={ann_state}")
    if persist_stats.get("vector_ann_warning"):
        ann_note = f"{ann_note}；{persist_stats['vector_ann_warning']}"
    method_label = "FastGraphRAG" if method == "fast" else "标准GraphRAG"
    kb.message = (
        f"{method_label} 索引完成：文本单元 {len(index.text_units)}，实体 {len(index.entities)}，"
        f"关系 {len(index.relationships)}，社区 {len(communities)}，报告 {len(reports)}"
        + (f"，声明 {len(index.covariates)}" if index.covariates else "")
        + f"；社区算法={community_stats.get('algorithm')}；"
        f"溯源实体 {provenance_stats.get('entities_with_sources', 0)}/{len(index.entities)}；"
        f"{ann_note}。"
    )
    summary = {
        "message": kb.message,
        "indexing_method": method,
        "chunk": chunk_stats,
        "extract": extract_stats,
        "communities": community_stats,
        "index": index.stats(),
        "provenance": provenance_stats,
        "persist": persist_stats,
        "pipeline": "microsoft_graphrag_compatible_v3",
        "phases": [
            *extract_phases,
            "hierarchical_community_detection",
            "community_reports_generate_and_summarize",
            "link_provenance_bidirectional",
            "text_embeddings",
            "persist_knowledge_model",
            "ensure_vector_indexes",
        ],
    }
    return kb, index, summary

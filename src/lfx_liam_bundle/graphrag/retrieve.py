"""统一检索入口：Local / Global / DRIFT Search。"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.drift_search import drift_search
from lfx_liam_bundle.graphrag.global_search import global_search
from lfx_liam_bundle.graphrag.local_search import local_search
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

SEARCH_MODES = ["Local Search", "Global Search", "DRIFT Search"]


def retrieve_documents(
    kb: GraphRAGKnowledgeBase,
    query: str,
    *,
    embedding: Embeddings | None = None,
    llm: Any | None = None,
    search_mode: str = "Local Search",
    community_level: int = 0,
    top_k_entities: int = 8,
    top_k_chunks: int = 6,
    answer_with_llm: bool = True,
    dynamic_community_selection: bool = False,
    max_context_tokens: int = 8000,
    text_unit_prop: float = 0.5,
    community_prop: float = 0.25,
    conversation_history: str | None = None,
    response_type: str = "Multi-paragraph answer",
    allow_general_knowledge: bool = False,
    map_concurrency: int = 1,
    drift_n_depth: int = 2,
    drift_top_k_reports: int = 5,
    drift_max_follow_ups: int = 3,
) -> tuple[list[Document], str, dict[str, Any]]:
    if not (query or "").strip():
        msg = "Search query cannot be empty."
        raise ValueError(msg)
    if kb.status == "error":
        msg = f"Knowledge base is in an error state: {kb.message}"
        raise ValueError(msg)

    mode = (search_mode or "Local Search").strip()
    if mode == "Global Search":
        return global_search(
            kb,
            query,
            llm,
            community_level=community_level,
            dynamic_community_selection=dynamic_community_selection,
            max_data_tokens=max_context_tokens,
            conversation_history=conversation_history,
            response_type=response_type,
            allow_general_knowledge=allow_general_knowledge,
            map_concurrency=map_concurrency,
        )
    if mode == "DRIFT Search":
        if embedding is None:
            msg = "DRIFT Search requires an Embedding model."
            raise ValueError(msg)
        if llm is None:
            msg = "DRIFT Search requires an LLM connection."
            raise ValueError(msg)
        return drift_search(
            kb,
            query,
            embedding,
            llm,
            n_depth=drift_n_depth,
            top_k_reports=drift_top_k_reports,
            top_k_entities=top_k_entities,
            top_k_chunks=top_k_chunks,
            max_follow_ups=drift_max_follow_ups,
            max_context_tokens=max_context_tokens,
            text_unit_prop=text_unit_prop,
            community_prop=community_prop,
            conversation_history=conversation_history,
            response_type=response_type,
        )
    if mode == "Local Search":
        if embedding is None:
            msg = "Local Search requires an Embedding model. Connect Embedding."
            raise ValueError(msg)
        return local_search(
            kb,
            query,
            embedding,
            llm=llm,
            top_k_entities=top_k_entities,
            top_k_chunks=top_k_chunks,
            answer_with_llm=answer_with_llm,
            max_context_tokens=max_context_tokens,
            text_unit_prop=text_unit_prop,
            community_prop=community_prop,
            conversation_history=conversation_history,
            response_type=response_type,
        )
    msg = (
        f"Unsupported search mode: {mode}. "
        "Choose Local Search, Global Search, or DRIFT Search."
    )
    raise ValueError(msg)

"""统一检索入口：Local Search / Global Search。"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.global_search import global_search
from lfx_liam_bundle.graphrag.local_search import local_search
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

SEARCH_MODES = ["Local Search", "Global Search"]


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
) -> tuple[list[Document], str, dict[str, Any]]:
    if not (query or "").strip():
        msg = "检索问题不能为空。"
        raise ValueError(msg)
    if kb.status == "error":
        msg = f"知识库状态异常：{kb.message}"
        raise ValueError(msg)

    mode = (search_mode or "Local Search").strip()
    if mode == "Global Search":
        return global_search(
            kb,
            query,
            llm,
            community_level=community_level,
            dynamic_community_selection=dynamic_community_selection,
        )
    if mode == "Local Search":
        if embedding is None:
            msg = "Local Search 需要 Embedding 模型（实体描述向量检索）。请连接 Embedding。"
            raise ValueError(msg)
        return local_search(
            kb,
            query,
            embedding,
            llm=llm,
            top_k_entities=top_k_entities,
            top_k_chunks=top_k_chunks,
            answer_with_llm=answer_with_llm,
        )
    msg = f"不支持的检索模式：{mode}。请选择 Local Search 或 Global Search。"
    raise ValueError(msg)

"""统一 GraphRAG 检索入口。"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag import arango_adapter, astra_adapter
from lfx_liam_bundle.graphrag.edges import evaluate_edge_definition, parse_edge_definition
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def traversal_strategy_names() -> list[str]:
    try:
        import graph_retriever.strategies as strategies_module
    except ImportError:
        return ["Eager"]
    classes = inspect.getmembers(strategies_module, inspect.isclass)
    names = [name for name, cls in classes if ABC not in cls.__bases__]
    return names or ["Eager"]


def retrieve_documents(
    kb: GraphRAGKnowledgeBase,
    query: str,
    *,
    embedding: Embeddings | None = None,
    edge_definition: str | None = None,
    strategy: str = "Eager",
    strategy_kwargs: dict[str, Any] | None = None,
    top_k: int = 4,
    depth: int = 1,
) -> list[Document]:
    if not (query or "").strip():
        msg = "检索问题不能为空。"
        raise ValueError(msg)
    if kb.status == "error":
        msg = f"知识库状态异常：{kb.message}"
        raise ValueError(msg)

    edge_def = edge_definition or kb.edge_definition
    if kb.backend == "astradb":
        return _retrieve_astra(
            kb,
            query,
            embedding=embedding,
            edge_definition=edge_def,
            strategy=strategy,
            strategy_kwargs=strategy_kwargs or {},
        )
    if kb.backend == "arangodb":
        source_field, _ = parse_edge_definition(edge_def)
        return arango_adapter.retrieve(
            kb,
            query,
            embedding,
            top_k=top_k,
            depth=depth,
            edge_field=source_field,
        )
    msg = f"不支持的后端：{kb.backend}"
    raise ValueError(msg)


def _retrieve_astra(
    kb: GraphRAGKnowledgeBase,
    query: str,
    *,
    embedding: Embeddings | None,
    edge_definition: str,
    strategy: str,
    strategy_kwargs: dict[str, Any],
) -> list[Document]:
    try:
        import graph_retriever.strategies as strategies_module
        from langchain_graph_retriever import GraphRetriever
    except ImportError as e:
        msg = (
            "缺少 GraphRetriever 依赖。请安装：pip install langchain-graph-retriever graph-retriever "
            f"（原始错误：{e}）"
        )
        raise ImportError(msg) from e

    store = astra_adapter.build_vector_store(kb, embedding)
    if not hasattr(strategies_module, strategy):
        msg = f"未知遍历策略「{strategy}」。可选：{', '.join(traversal_strategy_names())}"
        raise ValueError(msg)
    strategy_class = getattr(strategies_module, strategy)
    retriever = GraphRetriever(
        store=store,
        edges=[evaluate_edge_definition(edge_definition)],
        strategy=strategy_class(**strategy_kwargs),
    )
    return list(retriever.invoke(query))

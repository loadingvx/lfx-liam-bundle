"""AstraDB adapter：连接、入库索引、供 GraphRetriever 使用。"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def _require_astra_deps() -> None:
    try:
        import astrapy  # noqa: F401
        import langchain_astradb  # noqa: F401
    except ImportError as e:
        msg = (
            "缺少 AstraDB 依赖。请安装：pip install 'langchain-astradb' 'astrapy' "
            f"（原始错误：{e}）"
        )
        raise ImportError(msg) from e


def connect_and_probe(
    kb: GraphRAGKnowledgeBase, *, create_if_missing: bool = True
) -> GraphRAGKnowledgeBase:
    _require_astra_deps()
    from astrapy import DataAPIClient

    if not kb.api_endpoint or not kb.token:
        msg = "AstraDB 需要填写 API Endpoint 与 Token。"
        raise ValueError(msg)
    if not kb.collection_name:
        msg = "请填写集合名称（Collection）。"
        raise ValueError(msg)

    try:
        client = DataAPIClient(kb.token)
        database = client.get_database(
            kb.api_endpoint, token=kb.token, keyspace=kb.keyspace or None
        )
        names = list(database.list_collection_names())
        if kb.collection_name not in names:
            if not create_if_missing:
                msg = f"集合「{kb.collection_name}」不存在。请勾选创建或先在 Astra 控制台创建。"
                raise ValueError(msg)
            database.create_collection(kb.collection_name)
            kb.message = f"已创建集合「{kb.collection_name}」。"
            kb.status = "empty"
            kb.document_count = 0
        else:
            collection = database.get_collection(kb.collection_name)
            try:
                # estimated count if available
                count = collection.count_documents({}, upper_bound=1000)
                kb.document_count = int(count) if isinstance(count, int) else 0
            except Exception:
                kb.document_count = 0
            kb.status = "ready" if kb.document_count > 0 else "empty"
            kb.message = (
                f"已连接 AstraDB 集合「{kb.collection_name}」，当前约 {kb.document_count} 条文档。"
            )
    except ValueError:
        raise
    except Exception as e:
        msg = f"连接 AstraDB 失败：{e}"
        raise ValueError(msg) from e
    return kb


def build_vector_store(kb: GraphRAGKnowledgeBase, embedding: Embeddings | None):
    _require_astra_deps()
    from langchain_astradb import AstraDBVectorStore

    return AstraDBVectorStore(
        embedding=embedding,
        collection_name=kb.collection_name,
        token=kb.token,
        api_endpoint=kb.api_endpoint,
        namespace=kb.keyspace or None,
    )


def ingest_documents(
    kb: GraphRAGKnowledgeBase,
    documents: list[Document],
    embedding: Embeddings | None,
    *,
    mode: str = "按文档ID覆盖",
) -> tuple[GraphRAGKnowledgeBase, dict[str, Any]]:
    if not documents:
        msg = "没有可入库的文档。请检查上游是否输出了文本内容。"
        raise ValueError(msg)
    if embedding is None:
        msg = "AstraDB 入库需要 Embedding 模型（除非集合已配置 Vectorize，当前实现仍要求连接 Embedding）。"
        raise ValueError(msg)

    store = build_vector_store(kb, embedding)
    skipped = 0
    to_add = documents

    if mode == "按文档ID覆盖":
        ids = [d.id or d.metadata.get("doc_id") for d in documents]
        ids = [i for i in ids if i]
        if ids:
            try:
                store.delete(ids=ids)
            except Exception:
                # 删除失败不阻断写入（可能文档尚不存在）
                skipped = 0

    store.add_documents(to_add, ids=[d.id or d.metadata.get("doc_id") for d in to_add])
    kb.document_count = max(kb.document_count, 0) + len(to_add)
    kb.status = "ready"
    kb.message = f"已入库 {len(to_add)} 条文档到 AstraDB「{kb.collection_name}」。"
    summary = {
        "ingested": len(to_add),
        "skipped": skipped,
        "mode": mode,
        "backend": "astradb",
        "message": kb.message,
    }
    return kb, summary


def delete_by_ids(
    kb: GraphRAGKnowledgeBase, doc_ids: list[str], embedding: Embeddings | None
) -> dict[str, Any]:
    if not doc_ids:
        msg = "请提供要删除的文档 ID（doc_id）。"
        raise ValueError(msg)
    store = build_vector_store(kb, embedding)
    store.delete(ids=doc_ids)
    kb.message = f"已删除 {len(doc_ids)} 条文档。"
    return {"deleted": len(doc_ids), "message": kb.message}


def clear_collection(kb: GraphRAGKnowledgeBase) -> dict[str, Any]:
    _require_astra_deps()
    from astrapy import DataAPIClient

    client = DataAPIClient(kb.token)
    database = client.get_database(kb.api_endpoint, token=kb.token, keyspace=kb.keyspace or None)
    database.drop_collection(kb.collection_name)
    database.create_collection(kb.collection_name)
    kb.document_count = 0
    kb.status = "empty"
    kb.message = f"已清空并重建集合「{kb.collection_name}」。"
    return {"cleared": True, "message": kb.message}


def count_documents(kb: GraphRAGKnowledgeBase) -> int:
    _require_astra_deps()
    from astrapy import DataAPIClient

    client = DataAPIClient(kb.token)
    database = client.get_database(kb.api_endpoint, token=kb.token, keyspace=kb.keyspace or None)
    collection = database.get_collection(kb.collection_name)
    try:
        return int(collection.count_documents({}, upper_bound=100000))
    except Exception:
        return kb.document_count

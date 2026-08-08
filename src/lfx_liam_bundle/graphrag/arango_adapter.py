"""ArangoDB adapter：文档+向量+实体图。"""

from __future__ import annotations

import math
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.edges import _as_str_list
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def _require_arango() -> None:
    try:
        import arango  # noqa: F401
    except ImportError as e:
        msg = f"缺少 ArangoDB 依赖。请安装：pip install python-arango（原始错误：{e}）"
        raise ImportError(msg) from e


def _db(kb: GraphRAGKnowledgeBase):
    _require_arango()
    from arango import ArangoClient

    if not kb.arango_url:
        msg = "ArangoDB 需要填写服务地址（如 http://localhost:8529）。"
        raise ValueError(msg)
    client = ArangoClient(hosts=kb.arango_url)
    sys_db = client.db(
        "_system",
        username=kb.arango_username or "root",
        password=kb.arango_password or "",
    )
    db_name = kb.arango_database or "_system"
    if db_name != "_system" and not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    return client.db(
        db_name,
        username=kb.arango_username or "root",
        password=kb.arango_password or "",
    )


def _chunk_collection(kb: GraphRAGKnowledgeBase) -> str:
    return kb.collection_name or "liam_chunks"


def _entity_collection(kb: GraphRAGKnowledgeBase) -> str:
    return f"{_chunk_collection(kb)}_entities"


def _edge_collection(kb: GraphRAGKnowledgeBase) -> str:
    return f"{_chunk_collection(kb)}_links"


def ensure_schema(kb: GraphRAGKnowledgeBase, *, create_if_missing: bool = True) -> GraphRAGKnowledgeBase:
    db = _db(kb)
    chunk_col = _chunk_collection(kb)
    entity_col = _entity_collection(kb)
    edge_col = _edge_collection(kb)

    try:
        if not db.has_collection(chunk_col):
            if not create_if_missing:
                msg = f"集合「{chunk_col}」不存在。请勾选创建。"
                raise ValueError(msg)
            db.create_collection(chunk_col)
        if not db.has_collection(entity_col):
            db.create_collection(entity_col)
        if not db.has_collection(edge_col):
            db.create_collection(edge_col, edge=True)

        graph_name = kb.graph_name or f"{chunk_col}_graph"
        kb.graph_name = graph_name
        if not db.has_graph(graph_name):
            db.create_graph(
                graph_name,
                edge_definitions=[
                    {
                        "edge_collection": edge_col,
                        "from_vertex_collections": [chunk_col, entity_col],
                        "to_vertex_collections": [chunk_col, entity_col],
                    }
                ],
            )
        count = db.collection(chunk_col).count()
        kb.document_count = int(count or 0)
        kb.status = "ready" if kb.document_count > 0 else "empty"
        kb.message = f"已连接 ArangoDB「{kb.arango_database}/{chunk_col}」，文档数={kb.document_count}。"
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        msg = f"连接或初始化 ArangoDB 失败：{e}"
        raise ValueError(msg) from e
    return kb


def connect_and_probe(kb: GraphRAGKnowledgeBase, *, create_if_missing: bool = True) -> GraphRAGKnowledgeBase:
    return ensure_schema(kb, create_if_missing=create_if_missing)


def _entity_key(name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name.strip())[:64]
    return safe or "entity"


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
        msg = "ArangoDB 入库需要 Embedding 模型以构建向量索引。"
        raise ValueError(msg)

    kb = ensure_schema(kb, create_if_missing=True)
    db = _db(kb)
    chunk_col = db.collection(_chunk_collection(kb))
    entity_col = db.collection(_entity_collection(kb))
    edge_col = db.collection(_edge_collection(kb))

    texts = [d.page_content for d in documents]
    vectors = embedding.embed_documents(texts)
    if vectors and kb.embedding_dim is None:
        kb.embedding_dim = len(vectors[0])

    ingested = 0
    for doc, vector in zip(documents, vectors, strict=True):
        doc_id = str(doc.id or doc.metadata.get("doc_id"))
        key = doc_id.replace("/", "_")
        body = {
            "_key": key,
            "doc_id": doc_id,
            "text": doc.page_content,
            "metadata": doc.metadata,
            "entities": _as_str_list(doc.metadata.get("entities")),
            "keywords": _as_str_list(doc.metadata.get("keywords")),
            "embedding": vector,
        }
        if mode == "按文档ID覆盖" and chunk_col.has(key):
            chunk_col.delete(key)
            # 清理旧边（忽略失败）
            try:
                db.aql.execute(
                    "FOR e IN @@edge FILTER e._from == @from OR e._to == @to REMOVE e IN @@edge",
                    bind_vars={
                        "@edge": _edge_collection(kb),
                        "from": f"{_chunk_collection(kb)}/{key}",
                        "to": f"{_chunk_collection(kb)}/{key}",
                    },
                )
            except Exception:  # noqa: BLE001
                pass
        chunk_col.insert(body, overwrite=True, overwrite_mode="replace")
        ingested += 1

        # 实体顶点 + chunk-entity 边（用于图遍历）
        for field in ("entities", "keywords"):
            for ent in _as_str_list(doc.metadata.get(field)):
                ek = _entity_key(f"{field}_{ent}")
                if not entity_col.has(ek):
                    entity_col.insert({"_key": ek, "name": ent, "field": field}, silent=True)
                edge_key = f"{key}__{ek}"
                if not edge_col.has(edge_key):
                    edge_col.insert(
                        {
                            "_key": edge_key,
                            "_from": f"{_chunk_collection(kb)}/{key}",
                            "_to": f"{_entity_collection(kb)}/{ek}",
                            "field": field,
                        },
                        silent=True,
                    )

    kb.document_count = int(chunk_col.count() or 0)
    kb.status = "ready"
    kb.message = f"已入库 {ingested} 条文档到 ArangoDB「{_chunk_collection(kb)}」。"
    return kb, {"ingested": ingested, "skipped": 0, "mode": mode, "backend": "arangodb", "message": kb.message}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


def retrieve(
    kb: GraphRAGKnowledgeBase,
    query: str,
    embedding: Embeddings | None,
    *,
    top_k: int = 4,
    depth: int = 1,
    edge_field: str = "entities",
) -> list[Document]:
    if not (query or "").strip():
        return []
    if embedding is None:
        msg = "ArangoDB 检索需要 Embedding 模型。"
        raise ValueError(msg)

    kb = ensure_schema(kb, create_if_missing=False)
    db = _db(kb)
    chunk_name = _chunk_collection(kb)
    qvec = embedding.embed_query(query)

    cursor = db.aql.execute(f"FOR d IN {chunk_name} RETURN d")
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc in cursor:
        emb = doc.get("embedding") or []
        score = _cosine(qvec, emb)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    seeds = scored[: max(top_k, 1)]

    selected: dict[str, dict[str, Any]] = {}
    for score, doc in seeds:
        selected[doc["_id"]] = {**doc, "_score": score}

    # 图扩展：经实体/关键词边找邻居 chunk
    if depth > 0 and seeds:
        edge_col = _edge_collection(kb)
        entity_col = _entity_collection(kb)
        for _, seed in seeds:
            seed_id = seed["_id"]
            aql = """
            FOR v, e, p IN 1..@depth ANY @start GRAPH @graph
              OPTIONS {uniqueVertices: 'global'}
              FILTER IS_SAME_COLLECTION(@chunk, v) OR IS_SAME_COLLECTION(@entity, v)
              RETURN {v, e}
            """
            try:
                rows = db.aql.execute(
                    aql,
                    bind_vars={
                        "depth": depth,
                        "start": seed_id,
                        "graph": kb.graph_name or f"{chunk_name}_graph",
                        "chunk": chunk_name,
                        "entity": entity_col,
                    },
                )
                entity_keys = []
                for row in rows:
                    v = row.get("v") or {}
                    if v.get("_id", "").startswith(f"{entity_col}/"):
                        # field filter soft match
                        if edge_field and v.get("field") and v.get("field") != edge_field:
                            # still allow keywords/entities both
                            pass
                        entity_keys.append(v["_id"])
                if entity_keys:
                    neigh = db.aql.execute(
                        """
                        FOR e IN @@edge
                          FILTER e._to IN @ents OR e._from IN @ents
                          LET other = e._from IN @ents ? e._to : e._from
                          FILTER IS_SAME_COLLECTION(@chunk, other)
                          LET doc = DOCUMENT(other)
                          RETURN doc
                        """,
                        bind_vars={"@edge": edge_col, "ents": entity_keys, "chunk": chunk_name},
                    )
                    for doc in neigh:
                        if doc and doc.get("_id") not in selected:
                            selected[doc["_id"]] = {**doc, "_score": 0.0}
            except Exception:  # noqa: BLE001
                # 无图或图查询失败时退回纯向量结果
                break

    ordered = sorted(selected.values(), key=lambda d: d.get("_score", 0.0), reverse=True)[:top_k]
    results: list[Document] = []
    for doc in ordered:
        meta = dict(doc.get("metadata") or {})
        meta["doc_id"] = doc.get("doc_id")
        meta["entities"] = doc.get("entities") or meta.get("entities") or []
        meta["keywords"] = doc.get("keywords") or meta.get("keywords") or []
        meta["score"] = doc.get("_score")
        results.append(
            Document(
                page_content=doc.get("text") or "",
                metadata=meta,
                id=doc.get("doc_id"),
            )
        )
    return results


def delete_by_ids(kb: GraphRAGKnowledgeBase, doc_ids: list[str]) -> dict[str, Any]:
    if not doc_ids:
        msg = "请提供要删除的文档 ID（doc_id）。"
        raise ValueError(msg)
    db = _db(kb)
    col = db.collection(_chunk_collection(kb))
    deleted = 0
    for doc_id in doc_ids:
        key = str(doc_id).replace("/", "_")
        if col.has(key):
            col.delete(key)
            deleted += 1
    kb.document_count = int(col.count() or 0)
    kb.message = f"已删除 {deleted} 条文档。"
    kb.status = "ready" if kb.document_count else "empty"
    return {"deleted": deleted, "message": kb.message}


def clear_collection(kb: GraphRAGKnowledgeBase) -> dict[str, Any]:
    db = _db(kb)
    for name in (_chunk_collection(kb), _entity_collection(kb), _edge_collection(kb)):
        if db.has_collection(name):
            db.delete_collection(name)
    graph_name = kb.graph_name or f"{_chunk_collection(kb)}_graph"
    if db.has_graph(graph_name):
        db.delete_graph(graph_name, drop_collections=False)
    ensure_schema(kb, create_if_missing=True)
    kb.document_count = 0
    kb.status = "empty"
    kb.message = f"已清空知识库「{_chunk_collection(kb)}」。"
    return {"cleared": True, "message": kb.message}


def count_documents(kb: GraphRAGKnowledgeBase) -> int:
    db = _db(kb)
    if not db.has_collection(_chunk_collection(kb)):
        return 0
    return int(db.collection(_chunk_collection(kb)).count() or 0)

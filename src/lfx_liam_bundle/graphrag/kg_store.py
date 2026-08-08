"""将 GraphIndex 持久化到 AstraDB / ArangoDB。"""

from __future__ import annotations

from typing import Any

from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.models import (
    Community,
    CommunityReport,
    Covariate,
    DocumentRecord,
    Entity,
    GraphIndex,
    Relationship,
    TextUnit,
)
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def _base_name(kb: GraphRAGKnowledgeBase) -> str:
    """集合前缀：去掉用户误填的 _chunks 后缀，避免 liam_xxx_chunks_chunks。"""
    base = (kb.collection_name or "liam_graphrag").strip()
    for suffix in (
        "_chunks",
        "_entities",
        "_relationships",
        "_communities",
        "_reports",
        "_covariates",
    ):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base or "liam_graphrag"


def _names(kb: GraphRAGKnowledgeBase) -> dict[str, str]:
    base = _base_name(kb)
    return {
        "chunks": f"{base}_chunks",
        "entities": f"{base}_entities",
        "relationships": f"{base}_relationships",
        "communities": f"{base}_communities",
        "reports": f"{base}_reports",
        "covariates": f"{base}_covariates",
        "documents": f"{base}_documents",
        "edges": f"{base}_entity_edges",
    }


def ensure_kg_schema(kb: GraphRAGKnowledgeBase, *, create_if_missing: bool = True) -> None:
    names = _names(kb)
    if kb.backend == "astradb":
        _astra_ensure(kb, names, create_if_missing=create_if_missing)
    elif kb.backend == "arangodb":
        _arango_ensure(kb, names, create_if_missing=create_if_missing)
    else:
        msg = f"不支持的后端：{kb.backend}。请选择 AstraDB 或 ArangoDB。"
        raise ValueError(msg)


def persist_index(
    kb: GraphRAGKnowledgeBase,
    index: GraphIndex,
    embedding: Embeddings | None,
    *,
    replace: bool = True,
) -> dict[str, Any]:
    ensure_kg_schema(kb, create_if_missing=True)
    if embedding is not None:
        _embed_index(index, embedding)
    if kb.backend == "astradb":
        return _astra_persist(kb, index, replace=replace)
    return _arango_persist(kb, index, replace=replace)


def load_index(kb: GraphRAGKnowledgeBase) -> GraphIndex:
    ensure_kg_schema(kb, create_if_missing=False)
    if kb.backend == "astradb":
        return _astra_load(kb)
    return _arango_load(kb)


def clear_index(kb: GraphRAGKnowledgeBase) -> dict[str, Any]:
    """清空 GraphRAG 知识模型相关集合。"""
    names = _names(kb)
    ensure_kg_schema(kb, create_if_missing=True)
    if kb.backend == "astradb":
        db = _astra_db(kb)
        for key, name in names.items():
            if key == "edges":
                continue
            try:
                db.get_collection(name).delete_many({})
            except Exception:
                pass
    else:
        db = _arango_db(kb)
        for name in names.values():
            if db.has_collection(name):
                db.collection(name).truncate()
    kb.document_count = 0
    kb.status = "empty"
    kb.message = (
        "已清空 GraphRAG 知识库"
        "（documents/chunks/entities/relationships/communities/reports/covariates）。"
    )
    return {"cleared": True, "message": kb.message, "collections": names}


def _embed_index(index: GraphIndex, embedding: Embeddings) -> None:
    unit_texts = [u.text for u in index.text_units if not u.embedding]
    if unit_texts:
        vectors = embedding.embed_documents(unit_texts)
        i = 0
        for u in index.text_units:
            if not u.embedding:
                u.embedding = vectors[i]
                i += 1
    ent_texts = [
        f"{e.title}: {e.description}" for e in index.entities if not e.description_embedding
    ]
    if ent_texts:
        vectors = embedding.embed_documents(ent_texts)
        i = 0
        for e in index.entities:
            if not e.description_embedding:
                e.description_embedding = vectors[i]
                i += 1
    rep_texts = [
        f"{r.title}\n{r.summary}\n{r.full_content}"
        for r in index.community_reports
        if not r.embedding
    ]
    if rep_texts:
        vectors = embedding.embed_documents(rep_texts)
        i = 0
        for r in index.community_reports:
            if not r.embedding:
                r.embedding = vectors[i]
                i += 1


# ----- Astra -----


def _astra_db(kb: GraphRAGKnowledgeBase):
    from astrapy import DataAPIClient

    if not kb.api_endpoint or not kb.token:
        msg = "AstraDB 需要填写 API Endpoint 与 Token。"
        raise ValueError(msg)
    client = DataAPIClient(kb.token)
    return client.get_database(kb.api_endpoint, token=kb.token, keyspace=kb.keyspace or None)


def _astra_ensure(
    kb: GraphRAGKnowledgeBase, names: dict[str, str], *, create_if_missing: bool
) -> None:
    db = _astra_db(kb)
    existing = set(db.list_collection_names())
    for key, name in names.items():
        if key == "edges":
            continue
        if name not in existing:
            if not create_if_missing:
                msg = f"Astra 集合「{name}」不存在。请开启「不存在则创建」，或先在控制台建好集合。"
                raise ValueError(msg)
            db.create_collection(name)


def _astra_replace_collection(db, name: str, docs: list[dict[str, Any]]) -> None:
    col = db.get_collection(name)
    try:
        col.delete_many({})
    except Exception:
        pass
    if docs:
        col.insert_many(docs)


def _astra_persist(
    kb: GraphRAGKnowledgeBase, index: GraphIndex, *, replace: bool
) -> dict[str, Any]:
    db = _astra_db(kb)
    names = _names(kb)
    payload = {
        names["chunks"]: [{"_id": u.id, **u.to_dict()} for u in index.text_units],
        names["entities"]: [{"_id": e.id, **e.to_dict()} for e in index.entities],
        names["relationships"]: [{"_id": r.id, **r.to_dict()} for r in index.relationships],
        names["communities"]: [{"_id": c.id, **c.to_dict()} for c in index.communities],
        names["reports"]: [{"_id": r.id, **r.to_dict()} for r in index.community_reports],
        names["covariates"]: [{"_id": c.id, **c.to_dict()} for c in index.covariates],
        names["documents"]: [{"_id": d.id, **d.to_dict()} for d in index.documents],
    }
    if replace:
        for name, docs in payload.items():
            _astra_replace_collection(db, name, docs)
    else:
        for name, docs in payload.items():
            if docs:
                db.get_collection(name).insert_many(docs)
    return {"backend": "astradb", **index.stats(), "collections": names}


def _astra_load_all(col) -> list[dict[str, Any]]:
    try:
        return list(col.find({}))
    except Exception:
        return list(col.find({}, limit=100000))


def _astra_load(kb: GraphRAGKnowledgeBase) -> GraphIndex:
    db = _astra_db(kb)
    names = _names(kb)

    def _safe(name: str) -> list[dict[str, Any]]:
        try:
            return _astra_load_all(db.get_collection(name))
        except Exception:
            return []

    return _dicts_to_index(
        _safe(names["chunks"]),
        _safe(names["entities"]),
        _safe(names["relationships"]),
        _safe(names["communities"]),
        _safe(names["reports"]),
        _safe(names["covariates"]),
        _safe(names["documents"]),
    )


# ----- Arango -----


def _arango_db(kb: GraphRAGKnowledgeBase):
    from arango import ArangoClient

    if not kb.arango_url:
        msg = "ArangoDB 需要填写服务地址（如 http://localhost:8529）。"
        raise ValueError(msg)
    client = ArangoClient(hosts=kb.arango_url)
    sys_db = client.db(
        "_system", username=kb.arango_username or "root", password=kb.arango_password or ""
    )
    db_name = kb.arango_database or "_system"
    if db_name != "_system" and not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    return client.db(
        db_name, username=kb.arango_username or "root", password=kb.arango_password or ""
    )


def _arango_ensure(
    kb: GraphRAGKnowledgeBase, names: dict[str, str], *, create_if_missing: bool
) -> None:
    db = _arango_db(kb)
    for key, name in names.items():
        edge = key == "edges"
        if not db.has_collection(name):
            if not create_if_missing:
                msg = f"Arango 集合「{name}」不存在。请开启「不存在则创建」。"
                raise ValueError(msg)
            db.create_collection(name, edge=edge)
    graph_name = kb.graph_name or f"{_base_name(kb)}_kg_graph"
    kb.graph_name = graph_name
    if not db.has_graph(graph_name):
        db.create_graph(
            graph_name,
            edge_definitions=[
                {
                    "edge_collection": names["edges"],
                    "from_vertex_collections": [names["entities"]],
                    "to_vertex_collections": [names["entities"]],
                }
            ],
        )


def _safe_key(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)[:64] or "x"


def _arango_persist(
    kb: GraphRAGKnowledgeBase, index: GraphIndex, *, replace: bool
) -> dict[str, Any]:
    db = _arango_db(kb)
    names = _names(kb)
    if replace:
        for name in names.values():
            if db.has_collection(name):
                db.collection(name).truncate()

    def _ins(col_name: str, docs: list[dict[str, Any]]) -> None:
        col = db.collection(col_name)
        for d in docs:
            key = _safe_key(str(d.get("id") or d.get("_key")))
            payload = {**d, "_key": key}
            col.insert(payload, overwrite=True, overwrite_mode="replace")

    _ins(names["chunks"], [u.to_dict() for u in index.text_units])
    _ins(names["entities"], [e.to_dict() for e in index.entities])
    _ins(names["relationships"], [r.to_dict() for r in index.relationships])
    _ins(names["communities"], [c.to_dict() for c in index.communities])
    _ins(names["reports"], [r.to_dict() for r in index.community_reports])
    _ins(names["covariates"], [c.to_dict() for c in index.covariates])
    _ins(names["documents"], [d.to_dict() for d in index.documents])

    id_by_title = {e.title: e.id for e in index.entities}
    # also map casefold titles
    for e in index.entities:
        id_by_title.setdefault("".join(e.title.split()).casefold(), e.id)
    edge_col = db.collection(names["edges"])
    for r in index.relationships:
        s = id_by_title.get(r.source) or id_by_title.get("".join(r.source.split()).casefold())
        t = id_by_title.get(r.target) or id_by_title.get("".join(r.target.split()).casefold())
        if not s or not t:
            continue
        sk, tk = _safe_key(s), _safe_key(t)
        edge_col.insert(
            {
                "_key": _safe_key(r.id),
                "_from": f"{names['entities']}/{sk}",
                "_to": f"{names['entities']}/{tk}",
                "description": r.description,
                "weight": r.weight,
            },
            overwrite=True,
            overwrite_mode="replace",
            silent=True,
        )
    return {"backend": "arangodb", **index.stats(), "collections": names}


def _arango_load(kb: GraphRAGKnowledgeBase) -> GraphIndex:
    db = _arango_db(kb)
    names = _names(kb)

    def _all(name: str) -> list[dict[str, Any]]:
        if not db.has_collection(name):
            return []
        # 集合名经我们生成，只含安全字符
        return list(db.aql.execute(f"FOR d IN `{name}` RETURN d"))

    return _dicts_to_index(
        _all(names["chunks"]),
        _all(names["entities"]),
        _all(names["relationships"]),
        _all(names["communities"]),
        _all(names["reports"]),
        _all(names["covariates"]),
        _all(names["documents"]),
    )


def _dicts_to_index(
    chunks: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    covariates: list[dict[str, Any]] | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> GraphIndex:
    def _take(cls, d: dict[str, Any]):
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        raw = {k: v for k, v in d.items() if not str(k).startswith("_")}
        raw["id"] = d.get("id") or d.get("_key") or raw.get("id")
        filtered = {k: v for k, v in raw.items() if k in allowed}
        # dataclass defaults for missing optional list fields
        return cls(**filtered)

    return GraphIndex(
        text_units=[_take(TextUnit, d) for d in chunks],
        entities=[_take(Entity, d) for d in entities],
        relationships=[_take(Relationship, d) for d in relationships],
        communities=[_take(Community, d) for d in communities],
        community_reports=[_take(CommunityReport, d) for d in reports],
        covariates=[_take(Covariate, d) for d in (covariates or [])],
        documents=[_take(DocumentRecord, d) for d in (documents or [])],
    )

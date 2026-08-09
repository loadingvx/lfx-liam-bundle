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
        msg = f"Unsupported backend: {kb.backend}. Choose AstraDB or ArangoDB."
        raise ValueError(msg)


def persist_index(
    kb: GraphRAGKnowledgeBase,
    index: GraphIndex,
    embedding: Embeddings | None,
    *,
    replace: bool = True,
) -> dict[str, Any]:
    from lfx_liam_bundle.graphrag.vector_search import (
        ensure_astra_vector_collection,
        ensure_vector_indexes,
        infer_embedding_dim,
    )

    ensure_kg_schema(kb, create_if_missing=True)
    if embedding is not None:
        _embed_index(index, embedding)
    dim = infer_embedding_dim(index)
    if dim:
        kb.embedding_dim = dim

    # Astra：entities/chunks/reports 必须是向量集合，写入时附带 $vector
    if kb.backend == "astradb" and kb.use_vector_index and dim:
        db = _astra_db(kb)
        names = _names(kb)
        metric = kb.metric or "cosine"
        for key in ("entities", "chunks", "reports"):
            ensure_astra_vector_collection(
                db,
                names[key],
                dim=dim,
                metric=metric,
                recreate=bool(replace),
            )

    if kb.backend == "astradb":
        stats = _astra_persist(kb, index, replace=replace)
    else:
        stats = _arango_persist(kb, index, replace=replace)

    if kb.use_vector_index and dim:
        try:
            stats["vector_indexes"] = ensure_vector_indexes(
                kb,
                dim=dim,
                entity_count=len(index.entities),
                chunk_count=len(index.text_units),
                report_count=len(index.community_reports),
            )
            stats["vector_ann"] = "ready"
        except Exception as e:
            # 入库数据已落盘；向量索引失败不吞掉，让用户立刻看见（可关 use_vector_index 或修服务器）
            if not kb.ann_fallback_exact:
                raise
            stats["vector_ann"] = "failed"
            stats["vector_ann_warning"] = (
                f"Vector index not ready; Local Search will fall back to exact cosine: {e}"
            )
    else:
        stats["vector_ann"] = "disabled"
    return stats


def load_index(kb: GraphRAGKnowledgeBase) -> GraphIndex:
    ensure_kg_schema(kb, create_if_missing=False)
    if kb.backend == "astradb":
        return _astra_load(kb)
    return _arango_load(kb)


def load_subgraph(
    kb: GraphRAGKnowledgeBase,
    *,
    entity_ids: list[str],
    include_neighbors: bool = True,
) -> GraphIndex:
    """按种子实体加载局部子图，避免 Local Search 每次全量拉库。

    包含：种子(+邻居)实体、相关关系/原文/社区/报告/声明/文档。
    若局部结果过空则回退 ``load_index``。
    """
    seeds = [str(x).strip() for x in entity_ids if str(x).strip()]
    if not seeds:
        return load_index(kb)
    ensure_kg_schema(kb, create_if_missing=False)
    try:
        if kb.backend == "astradb":
            partial = _astra_load_subgraph(kb, seeds, include_neighbors=include_neighbors)
        else:
            partial = _arango_load_subgraph(kb, seeds, include_neighbors=include_neighbors)
    except Exception:
        return load_index(kb)
    if not partial.entities:
        return load_index(kb)
    return partial


def _norm_title(title: str) -> str:
    return "".join((title or "").split()).casefold()


def _expand_entity_neighborhood(
    entities: list[Entity],
    relationships: list[Relationship],
    seed_ids: list[str],
    *,
    include_neighbors: bool,
) -> tuple[list[Entity], list[Relationship]]:
    by_id = {e.id: e for e in entities}
    seeds = [by_id[i] for i in seed_ids if i in by_id]
    if not seeds:
        return [], []
    seed_titles = {_norm_title(e.title) for e in seeds}
    seed_id_set = {e.id for e in seeds}
    rels = [
        r
        for r in relationships
        if _norm_title(r.source) in seed_titles or _norm_title(r.target) in seed_titles
    ]
    keep_ids = set(seed_id_set)
    if include_neighbors:
        neighbor_titles = {_norm_title(r.source) for r in rels} | {
            _norm_title(r.target) for r in rels
        }
        for e in entities:
            if _norm_title(e.title) in neighbor_titles:
                keep_ids.add(e.id)
    kept_entities = [by_id[i] for i in keep_ids if i in by_id]
    kept_titles = {_norm_title(e.title) for e in kept_entities}
    kept_rels = [
        r
        for r in relationships
        if _norm_title(r.source) in kept_titles or _norm_title(r.target) in kept_titles
    ]
    return kept_entities, kept_rels


def _slice_index_for_entities(
    full: GraphIndex,
    seed_ids: list[str],
    *,
    include_neighbors: bool,
) -> GraphIndex:
    entities, relationships = _expand_entity_neighborhood(
        full.entities, full.relationships, seed_ids, include_neighbors=include_neighbors
    )
    if not entities:
        return GraphIndex()
    unit_ids: list[str] = []
    community_ids: list[str] = []
    for e in entities:
        unit_ids.extend(e.text_unit_ids)
        community_ids.extend(e.community_ids)
    for r in relationships:
        unit_ids.extend(r.text_unit_ids or [])
    unit_ids = list(dict.fromkeys(unit_ids))
    community_ids = list(dict.fromkeys(community_ids))
    units = [u for u in full.text_units if u.id in set(unit_ids)]
    reports = [r for r in full.community_reports if r.community_id in set(community_ids)]
    communities = [c for c in full.communities if c.id in set(community_ids)]
    seed_titles = {_norm_title(e.title) for e in entities}
    covariates = [c for c in full.covariates if _norm_title(c.subject) in seed_titles]
    doc_ids = {u.document_id for u in units if u.document_id}
    documents = [d for d in full.documents if d.id in doc_ids]
    return GraphIndex(
        text_units=units,
        entities=entities,
        relationships=relationships,
        communities=communities,
        community_reports=reports,
        covariates=covariates,
        documents=documents,
    )


def _astra_load_by_ids(col, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    out: list[dict[str, Any]] = []
    # Data API 支持 $in；失败则逐条 get
    try:
        rows = list(col.find({"_id": {"$in": ids}}, limit=max(100, len(ids) * 2)))
        if rows:
            return rows
    except Exception:
        pass
    for i in ids:
        try:
            doc = col.find_one({"_id": i})
            if doc:
                out.append(doc)
                continue
        except Exception:
            pass
        try:
            doc = col.find_one({"id": i})
            if doc:
                out.append(doc)
        except Exception:
            continue
    return out


def _astra_load_subgraph(
    kb: GraphRAGKnowledgeBase, seed_ids: list[str], *, include_neighbors: bool
) -> GraphIndex:
    """Astra：按 id 拉取实体/原文等；关系集合通常较小，整表读后在内存过滤。"""
    db = _astra_db(kb)
    names = _names(kb)
    seed_docs = _astra_load_by_ids(db.get_collection(names["entities"]), seed_ids)
    if not seed_docs:
        return GraphIndex()

    try:
        rel_docs = _astra_load_all(db.get_collection(names["relationships"]))
    except Exception:
        rel_docs = []

    seed_titles = {
        "".join(str(d.get("title") or "").split()).casefold() for d in seed_docs
    }
    kept_rels = [
        d
        for d in rel_docs
        if "".join(str(d.get("source") or "").split()).casefold() in seed_titles
        or "".join(str(d.get("target") or "").split()).casefold() in seed_titles
    ]
    neighbor_titles = set(seed_titles)
    if include_neighbors:
        for d in kept_rels:
            neighbor_titles.add("".join(str(d.get("source") or "").split()).casefold())
            neighbor_titles.add("".join(str(d.get("target") or "").split()).casefold())
        # 邻居实体：关系表读完后，按需再扫实体集合（比全量 chunks 便宜）
        try:
            all_ents = _astra_load_all(db.get_collection(names["entities"]))
            ent_docs = [
                d
                for d in all_ents
                if "".join(str(d.get("title") or "").split()).casefold() in neighbor_titles
            ]
        except Exception:
            ent_docs = seed_docs
        # 扩展关系覆盖邻居
        kept_rels = [
            d
            for d in rel_docs
            if "".join(str(d.get("source") or "").split()).casefold() in neighbor_titles
            or "".join(str(d.get("target") or "").split()).casefold() in neighbor_titles
        ]
    else:
        ent_docs = seed_docs

    unit_ids: list[str] = []
    community_ids: list[str] = []
    for d in ent_docs:
        unit_ids.extend([str(x) for x in (d.get("text_unit_ids") or []) if x])
        community_ids.extend([str(x) for x in (d.get("community_ids") or []) if x])
    for d in kept_rels:
        unit_ids.extend([str(x) for x in (d.get("text_unit_ids") or []) if x])
    unit_ids = list(dict.fromkeys(unit_ids))
    community_ids = list(dict.fromkeys(community_ids))

    chunk_docs = _astra_load_by_ids(db.get_collection(names["chunks"]), unit_ids)
    community_docs = _astra_load_by_ids(db.get_collection(names["communities"]), community_ids)
    report_docs: list[dict[str, Any]] = []
    if community_ids:
        try:
            report_docs = list(
                db.get_collection(names["reports"]).find(
                    {"community_id": {"$in": community_ids}},
                    limit=max(50, len(community_ids) * 5),
                )
            )
        except Exception:
            try:
                report_docs = [
                    d
                    for d in _astra_load_all(db.get_collection(names["reports"]))
                    if str(d.get("community_id") or "") in set(community_ids)
                ]
            except Exception:
                report_docs = []
    cov_docs: list[dict[str, Any]] = []
    try:
        all_cov = _astra_load_all(db.get_collection(names["covariates"]))
        cov_docs = [
            d
            for d in all_cov
            if "".join(str(d.get("subject") or "").split()).casefold() in neighbor_titles
        ]
    except Exception:
        cov_docs = []
    doc_ids = list(
        dict.fromkeys(str(d.get("document_id")) for d in chunk_docs if d.get("document_id"))
    )
    document_docs = _astra_load_by_ids(db.get_collection(names["documents"]), doc_ids)
    return _dicts_to_index(
        chunk_docs,
        ent_docs,
        kept_rels,
        community_docs,
        report_docs,
        cov_docs,
        document_docs,
    )


def _arango_load_subgraph(
    kb: GraphRAGKnowledgeBase, seed_ids: list[str], *, include_neighbors: bool
) -> GraphIndex:
    db = _arango_db(kb)
    names = _names(kb)

    def _by_ids(col_name: str, ids: list[str], id_field: str = "id") -> list[dict[str, Any]]:
        if not ids or not db.has_collection(col_name):
            return []
        aql = f"""
        FOR d IN `{col_name}`
          FILTER d.`{id_field}` IN @ids OR d._key IN @ids
          RETURN d
        """
        return list(db.aql.execute(aql, bind_vars={"ids": ids}))

    seed_docs = _by_ids(names["entities"], seed_ids)
    if not seed_docs:
        return GraphIndex()
    # 关系：标题匹配需要先有种子标题
    seed_titles = [
        "".join(str(d.get("title") or "").split()).casefold() for d in seed_docs
    ]
    rel_docs: list[dict[str, Any]] = []
    if db.has_collection(names["relationships"]):
        aql = f"""
        FOR d IN `{names["relationships"]}`
          LET s = LOWER(SUBSTITUTE(d.source, " ", ""))
          LET t = LOWER(SUBSTITUTE(d.target, " ", ""))
          FILTER s IN @titles OR t IN @titles
          RETURN d
        """
        try:
            rel_docs = list(db.aql.execute(aql, bind_vars={"titles": seed_titles}))
        except Exception:
            rel_docs = list(db.aql.execute(f"FOR d IN `{names['relationships']}` RETURN d"))

    neighbor_titles = set(seed_titles)
    for d in rel_docs:
        neighbor_titles.add("".join(str(d.get("source") or "").split()).casefold())
        neighbor_titles.add("".join(str(d.get("target") or "").split()).casefold())

    ent_docs = seed_docs
    if include_neighbors and db.has_collection(names["entities"]):
        aql = f"""
        FOR d IN `{names["entities"]}`
          LET t = LOWER(SUBSTITUTE(d.title, " ", ""))
          FILTER t IN @titles
          RETURN d
        """
        try:
            ent_docs = list(db.aql.execute(aql, bind_vars={"titles": list(neighbor_titles)}))
        except Exception:
            ent_docs = seed_docs

    unit_ids: list[str] = []
    community_ids: list[str] = []
    for d in ent_docs:
        unit_ids.extend(d.get("text_unit_ids") or [])
        community_ids.extend(d.get("community_ids") or [])
    for d in rel_docs:
        unit_ids.extend(d.get("text_unit_ids") or [])
    unit_ids = list(dict.fromkeys(str(x) for x in unit_ids if x))
    community_ids = list(dict.fromkeys(str(x) for x in community_ids if x))

    chunk_docs = _by_ids(names["chunks"], unit_ids)
    community_docs = _by_ids(names["communities"], community_ids)
    report_docs: list[dict[str, Any]] = []
    if community_ids and db.has_collection(names["reports"]):
        aql = f"""
        FOR d IN `{names["reports"]}`
          FILTER d.community_id IN @cids
          RETURN d
        """
        report_docs = list(db.aql.execute(aql, bind_vars={"cids": community_ids}))
    cov_docs: list[dict[str, Any]] = []
    if db.has_collection(names["covariates"]):
        aql = f"""
        FOR d IN `{names["covariates"]}`
          LET s = LOWER(SUBSTITUTE(d.subject, " ", ""))
          FILTER s IN @titles
          RETURN d
        """
        try:
            cov_docs = list(db.aql.execute(aql, bind_vars={"titles": list(neighbor_titles)}))
        except Exception:
            cov_docs = []
    doc_ids = list(
        dict.fromkeys(str(d.get("document_id")) for d in chunk_docs if d.get("document_id"))
    )
    document_docs = _by_ids(names["documents"], doc_ids)
    return _dicts_to_index(
        chunk_docs,
        ent_docs,
        rel_docs,
        community_docs,
        report_docs,
        cov_docs,
        document_docs,
    )


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
        "Cleared GraphRAG knowledge base "
        "(documents/chunks/entities/relationships/communities/reports/covariates)."
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
    """连接 Astra 云或本地/自建 Data API（HCD）。"""
    from astrapy import DataAPIClient
    from astrapy.authentication import UsernamePasswordTokenProvider
    from astrapy.constants import Environment

    endpoint = (kb.api_endpoint or "").strip()
    if not endpoint:
        msg = "Astra/Data API requires an API Endpoint (cloud Astra or local http://host:8181)."
        raise ValueError(msg)

    env_name = (kb.data_api_environment or "astra").strip().lower()
    keyspace = (kb.keyspace or "default_keyspace").strip() or None

    if env_name == "hcd":
        user = (kb.data_api_username or "").strip()
        password = kb.data_api_password or ""
        if not user:
            msg = (
                "Local/self-hosted Data API (HCD) requires username and password. "
                "Configure advanced options on Knowledge Base, or set data_api_username/password."
            )
            raise ValueError(msg)
        token = UsernamePasswordTokenProvider(user, password)
        client = DataAPIClient(environment=Environment.HCD)
        return client.get_database(endpoint, token=token, keyspace=keyspace)

    token = (kb.token or "").strip()
    if not token:
        msg = "Cloud AstraDB requires an Application Token."
        raise ValueError(msg)
    client = DataAPIClient(token)
    return client.get_database(endpoint, token=token, keyspace=keyspace)


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
                msg = f"Astra collection 「{name}」 does not exist. Enable Create if missing, or create it in the console."
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


def _astra_doc(doc_id: str, data: dict[str, Any], vector: list[float] | None = None) -> dict[str, Any]:
    payload = {"_id": doc_id, **data}
    if vector:
        payload["$vector"] = vector
    return payload


def _astra_persist(
    kb: GraphRAGKnowledgeBase, index: GraphIndex, *, replace: bool
) -> dict[str, Any]:
    db = _astra_db(kb)
    names = _names(kb)
    use_ann = bool(kb.use_vector_index)
    payload = {
        names["chunks"]: [
            _astra_doc(u.id, u.to_dict(), u.embedding if use_ann else None)
            for u in index.text_units
        ],
        names["entities"]: [
            _astra_doc(e.id, e.to_dict(), e.description_embedding if use_ann else None)
            for e in index.entities
        ],
        names["relationships"]: [_astra_doc(r.id, r.to_dict()) for r in index.relationships],
        names["communities"]: [_astra_doc(c.id, c.to_dict()) for c in index.communities],
        names["reports"]: [
            _astra_doc(r.id, r.to_dict(), r.embedding if use_ann else None)
            for r in index.community_reports
        ],
        names["covariates"]: [_astra_doc(c.id, c.to_dict()) for c in index.covariates],
        names["documents"]: [_astra_doc(d.id, d.to_dict()) for d in index.documents],
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
        msg = "ArangoDB requires a service URL (e.g. http://localhost:8529)."
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
                msg = f"Arango collection 「{name}」 does not exist. Enable Create if missing."
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

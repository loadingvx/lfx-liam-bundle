"""后端向量 ANN：Astra `$vector` / Arango Faiss(IVF+HNSW) 近似检索。

入库后建立或刷新向量索引；Local Search 默认走 ANN，失败时回退进程内精确余弦。
"""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from lfx_liam_bundle.graphrag.kg_store import _arango_db, _astra_db, _names
from lfx_liam_bundle.graphrag.models import GraphIndex
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

AnnTarget = Literal["entities", "chunks", "reports"]

_TARGET_FIELD: dict[AnnTarget, str] = {
    "entities": "description_embedding",
    "chunks": "embedding",
    "reports": "embedding",
}


def infer_embedding_dim(index: GraphIndex) -> int | None:
    for e in index.entities:
        if e.description_embedding:
            return len(e.description_embedding)
    for u in index.text_units:
        if u.embedding:
            return len(u.embedding)
    for r in index.community_reports:
        if r.embedding:
            return len(r.embedding)
    return None


def choose_n_lists(n_docs: int, configured: int | None = None) -> int:
    """为 Arango IVF 选择 nLists：不得超过文档数，小库自动收缩。"""
    n = max(0, int(n_docs))
    if n <= 0:
        return 1
    if configured is not None and int(configured) > 0:
        return max(1, min(int(configured), n))
    if n < 50:
        return max(1, n // 2 or 1)
    return min(100, max(10, int(math.sqrt(n))))


def build_arango_factory(
    n_lists: int, template: str | None, *, n_docs: int = 0
) -> str:
    """生成 Faiss factory。

    小样本（<40 文档）强制 ``IVF{n},Flat``：Arango 3.12.4 实验向量索引在
    ``IVF*_HNSW*`` + 极少点时可能 SIGSEGV（已知 Faiss/HNSW 训练崩溃）。
    """
    n = max(1, int(n_lists))
    docs = max(0, int(n_docs))
    if docs > 0 and docs < 40:
        return f"IVF{n},Flat"
    raw = (template or "").strip()
    if not raw:
        return f"IVF{n}_HNSW10,Flat"
    updated = re.sub(r"IVF\d+", f"IVF{n}", raw, count=1)
    if updated == raw and not raw.upper().startswith("IVF"):
        return f"IVF{n}_{raw}"
    # 用户强制 HNSW 但样本仍很小：降级，避免打崩服务器
    if docs > 0 and docs < 40 and "HNSW" in updated.upper():
        return f"IVF{n},Flat"
    return updated


def ensure_vector_indexes(
    kb: GraphRAGKnowledgeBase,
    *,
    dim: int,
    entity_count: int = 0,
    chunk_count: int = 0,
    report_count: int = 0,
) -> dict[str, Any]:
    """入库后确保向量检索就绪。Astra 依赖向量集合；Arango 创建 Faiss 索引。"""
    if dim <= 0:
        msg = "向量维度无效。请确认 Embedding 模型已正确产出向量。"
        raise ValueError(msg)
    kb.embedding_dim = dim
    metric = (kb.metric or "cosine").strip().lower() or "cosine"
    if kb.backend == "astradb":
        return _astra_ensure_vector_ready(kb, dim=dim, metric=metric)
    if kb.backend == "arangodb":
        return _arango_ensure_vector_indexes(
            kb,
            dim=dim,
            metric=metric,
            entity_count=entity_count,
            chunk_count=chunk_count,
            report_count=report_count,
        )
    msg = f"不支持的后端：{kb.backend}。"
    raise ValueError(msg)


def ann_search(
    kb: GraphRAGKnowledgeBase,
    query_vec: list[float],
    *,
    target: AnnTarget,
    top_k: int = 8,
) -> list[tuple[str, float]]:
    """返回 [(id, score), ...]，分数越大越相似。"""
    if not query_vec:
        msg = "查询向量为空，无法做向量检索。请检查 Embedding 模型。"
        raise ValueError(msg)
    if top_k <= 0:
        return []
    if kb.embedding_dim and len(query_vec) != kb.embedding_dim:
        msg = (
            f"查询向量维度 {len(query_vec)} 与知识库记录维度 {kb.embedding_dim} 不一致。"
            "请使用与建库时相同的 Embedding 模型，或重新入库建图。"
        )
        raise ValueError(msg)
    if kb.backend == "astradb":
        return _astra_ann(kb, query_vec, target=target, top_k=top_k)
    if kb.backend == "arangodb":
        return _arango_ann(kb, query_vec, target=target, top_k=top_k)
    msg = f"不支持的后端：{kb.backend}。"
    raise ValueError(msg)


def ann_search_entities(
    kb: GraphRAGKnowledgeBase, query_vec: list[float], *, top_k: int = 8
) -> list[tuple[str, float]]:
    return ann_search(kb, query_vec, target="entities", top_k=top_k)


def ann_search_chunks(
    kb: GraphRAGKnowledgeBase, query_vec: list[float], *, top_k: int = 6
) -> list[tuple[str, float]]:
    return ann_search(kb, query_vec, target="chunks", top_k=top_k)


# ----- Astra -----


def _astra_metric(metric: str):
    from astrapy.constants import VectorMetric

    m = (metric or "cosine").lower()
    if m in {"cosine", "cos"}:
        return VectorMetric.COSINE
    if m in {"euclidean", "l2"}:
        return VectorMetric.EUCLIDEAN
    if m in {"dot_product", "dot", "innerproduct", "ip"}:
        return VectorMetric.DOT_PRODUCT
    return VectorMetric.COSINE


def astra_vector_collection_definition(dim: int, metric: str = "cosine"):
    from astrapy.info import CollectionDefinition

    return (
        CollectionDefinition.builder()
        .with_vector_dimension(int(dim))
        .with_vector_metric(_astra_metric(metric))
        .build()
    )


def ensure_astra_vector_collection(
    db, name: str, *, dim: int, metric: str = "cosine", recreate: bool = False
) -> dict[str, Any]:
    """确保 Astra 集合具备 `$vector` ANN 能力；维度不匹配时可重建。"""
    from astrapy.exceptions import DataAPIResponseException

    existing = set(db.list_collection_names())
    need_create = name not in existing
    if name in existing:
        col = db.get_collection(name)
        info = None
        try:
            info = col.info()
        except Exception:
            try:
                info = col.options()
            except Exception:
                info = None
        current_dim = _extract_astra_vector_dim(info)
        if current_dim == dim:
            return {
                "collection": name,
                "vector": True,
                "dimension": dim,
                "created": False,
            }
        if current_dim is not None and current_dim != dim:
            if not recreate:
                msg = (
                    f"Astra 集合「{name}」向量维度为 {current_dim}，与当前 Embedding "
                    f"维度 {dim} 不一致。请在入库建图勾选覆盖重建，或换回原 Embedding 模型。"
                )
                raise ValueError(msg)
        elif current_dim is None and not recreate:
            msg = (
                f"Astra 集合「{name}」还不是向量集合，无法启用 ANN。"
                "请在「入库建图」勾选覆盖重建（会重建为向量集合并写入 `$vector`）。"
            )
            raise ValueError(msg)
        try:
            db.drop_collection(name)
        except Exception:
            try:
                db.get_collection(name).drop()
            except DataAPIResponseException as e:
                msg = f"无法删除旧 Astra 集合「{name}」以升级为向量集合：{e}"
                raise ValueError(msg) from e
        need_create = True
    if need_create:
        db.create_collection(
            name, definition=astra_vector_collection_definition(dim, metric)
        )
        return {"collection": name, "vector": True, "dimension": dim, "created": True}
    return {
        "collection": name,
        "vector": True,
        "dimension": dim,
        "created": False,
    }


def _extract_astra_vector_dim(info: Any) -> int | None:
    if info is None:
        return None
    raw: Any = info
    if hasattr(info, "as_dict"):
        try:
            raw = info.as_dict()
        except Exception:
            raw = info
    if not isinstance(raw, dict):
        # CollectionDescriptor-like
        for attr in ("definition", "options", "vector"):
            val = getattr(info, attr, None)
            if val is not None:
                dim = _extract_astra_vector_dim(val)
                if dim is not None:
                    return dim
        dim = getattr(info, "dimension", None)
        return int(dim) if isinstance(dim, int) else None

    # nested shapes from Data API
    for key in ("definition", "options", "vector"):
        if key in raw and isinstance(raw[key], (dict, object)):
            dim = _extract_astra_vector_dim(raw[key])
            if dim is not None:
                return dim
    vector = raw.get("vector") if isinstance(raw, dict) else None
    if isinstance(vector, dict) and vector.get("dimension") is not None:
        return int(vector["dimension"])
    if raw.get("dimension") is not None:
        try:
            return int(raw["dimension"])
        except (TypeError, ValueError):
            return None
    return None


def _astra_ensure_vector_ready(
    kb: GraphRAGKnowledgeBase, *, dim: int, metric: str
) -> dict[str, Any]:
    db = _astra_db(kb)
    names = _names(kb)
    results = {}
    for key in ("entities", "chunks", "reports"):
        results[key] = ensure_astra_vector_collection(
            db, names[key], dim=dim, metric=metric, recreate=False
        )
    return {"backend": "astradb", "dimension": dim, "metric": metric, "indexes": results}


def _astra_ann(
    kb: GraphRAGKnowledgeBase,
    query_vec: list[float],
    *,
    target: AnnTarget,
    top_k: int,
) -> list[tuple[str, float]]:
    db = _astra_db(kb)
    name = _names(kb)[target]
    try:
        col = db.get_collection(name)
    except Exception as e:
        msg = f"Astra 集合「{name}」不可用，无法向量检索：{e}"
        raise ValueError(msg) from e
    try:
        cursor = col.find(
            {},
            sort={"$vector": query_vec},
            limit=int(top_k),
            include_similarity=True,
            projection={"_id": True, "id": True},
        )
        hits: list[tuple[str, float]] = []
        for doc in cursor:
            doc_id = str(doc.get("id") or doc.get("_id") or "").strip()
            if not doc_id:
                continue
            score = doc.get("$similarity")
            try:
                score_f = float(score) if score is not None else 0.0
            except (TypeError, ValueError):
                score_f = 0.0
            hits.append((doc_id, score_f))
        return hits
    except Exception as e:
        msg = (
            f"Astra 向量检索失败（集合 {name}）。"
            f"请确认集合已按向量维度创建，且文档含 `$vector`。详情：{e}"
        )
        raise ValueError(msg) from e


# ----- Arango -----


def _arango_ensure_vector_indexes(
    kb: GraphRAGKnowledgeBase,
    *,
    dim: int,
    metric: str,
    entity_count: int,
    chunk_count: int,
    report_count: int,
) -> dict[str, Any]:
    db = _arango_db(kb)
    names = _names(kb)
    factory_tmpl = (kb.vector_index_factory or "IVF100_HNSW10,Flat").strip()
    arango_metric = _arango_metric(metric)
    results: dict[str, Any] = {}
    specs: list[tuple[str, str, int]] = [
        (names["entities"], _TARGET_FIELD["entities"], entity_count),
        (names["chunks"], _TARGET_FIELD["chunks"], chunk_count),
        (names["reports"], _TARGET_FIELD["reports"], report_count),
    ]
    for col_name, field, count in specs:
        if not db.has_collection(col_name):
            results[col_name] = {"ok": False, "reason": "集合不存在"}
            continue
        if count <= 0:
            # 仍尝试按集合实际文档数
            try:
                count = int(db.collection(col_name).count())
            except Exception:
                count = 0
        if count <= 0:
            results[col_name] = {"ok": False, "reason": "无向量文档，跳过建索引"}
            continue
        n_lists = choose_n_lists(count, kb.vector_n_lists)
        factory = build_arango_factory(n_lists, factory_tmpl, n_docs=count)
        results[col_name] = _arango_add_vector_index(
            db.collection(col_name),
            field=field,
            dim=dim,
            metric=arango_metric,
            n_lists=n_lists,
            factory=factory,
        )
    return {
        "backend": "arangodb",
        "dimension": dim,
        "metric": arango_metric,
        "indexes": results,
    }


def _arango_metric(metric: str) -> str:
    m = (metric or "cosine").lower()
    if m in {"l2", "euclidean"}:
        return "l2"
    if m in {"innerproduct", "ip", "dot", "dot_product"}:
        return "innerProduct"
    return "cosine"


def _arango_add_vector_index(
    col,
    *,
    field: str,
    dim: int,
    metric: str,
    n_lists: int,
    factory: str,
) -> dict[str, Any]:
    # 删除同字段旧向量索引，避免维度/参数漂移
    try:
        for idx in col.indexes() or []:
            if idx.get("type") != "vector":
                continue
            fields = idx.get("fields") or []
            if field in fields or fields == [field]:
                idx_id = idx.get("id") or idx.get("name")
                if idx_id:
                    col.delete_index(str(idx_id), ignore_missing=True)
    except Exception:
        pass

    index_name = f"vec_{field}"[:64]
    payload = {
        "type": "vector",
        "name": index_name,
        "fields": [field],
        "params": {
            "metric": metric,
            "dimension": int(dim),
            "nLists": int(n_lists),
            "factory": factory,
            "defaultNProbe": int(min(max(1, n_lists), 10)),
        },
        "sparse": True,
    }
    try:
        created = col.add_index(payload)
        return {
            "ok": True,
            "field": field,
            "nLists": n_lists,
            "factory": factory,
            "index": created,
        }
    except Exception as e:
        msg = (
            f"Arango 集合「{col.name}」创建向量索引失败。"
            "请确认服务器已启用 `--vector-index`，版本支持 Faiss 向量索引，"
            f"且文档数不少于 nLists（当前 nLists={n_lists}）。详情：{e}"
        )
        raise ValueError(msg) from e


def _arango_ann(
    kb: GraphRAGKnowledgeBase,
    query_vec: list[float],
    *,
    target: AnnTarget,
    top_k: int,
) -> list[tuple[str, float]]:
    db = _arango_db(kb)
    col_name = _names(kb)[target]
    field = _TARGET_FIELD[target]
    if not db.has_collection(col_name):
        msg = f"Arango 集合「{col_name}」不存在，无法向量检索。"
        raise ValueError(msg)

    metric = _arango_metric(kb.metric or "cosine")
    if metric == "l2":
        sort_expr = f"APPROX_NEAR_L2(d.`{field}`, @q)"
        sort_dir = "ASC"
    elif metric == "innerProduct":
        sort_expr = f"APPROX_NEAR_INNER_PRODUCT(d.`{field}`, @q)"
        sort_dir = "DESC"
    else:
        sort_expr = f"APPROX_NEAR_COSINE(d.`{field}`, @q)"
        sort_dir = "DESC"

    # 不用 FILTER：Arango 3.12.4/5 的向量查询对 FOR→SORT 间 FILTER 支持不完整；
    # sparse 向量索引本身会跳过无向量字段文档。
    aql = f"""
    FOR d IN `{col_name}`
      LET score = {sort_expr}
      SORT score {sort_dir}
      LIMIT @k
      RETURN {{ id: d.id, key: d._key, score: score }}
    """
    try:
        rows = list(db.aql.execute(aql, bind_vars={"q": query_vec, "k": int(top_k)}))
    except Exception as e:
        msg = (
            f"Arango 向量检索失败（集合 {col_name}，字段 {field}）。"
            "请先完成入库建图以创建向量索引，并确认服务器开启了 vector index。"
            f"详情：{e}"
        )
        raise ValueError(msg) from e

    hits: list[tuple[str, float]] = []
    for row in rows:
        doc_id = str(row.get("id") or row.get("key") or "").strip()
        if not doc_id:
            continue
        try:
            score_f = float(row.get("score"))
        except (TypeError, ValueError):
            score_f = 0.0
        hits.append((doc_id, score_f))
    return hits

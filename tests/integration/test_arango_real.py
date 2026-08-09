"""ArangoDB 真库集成测试：schema / 落库 / 向量索引 / ANN / 子图 / Local Search / 清空。"""

from __future__ import annotations

import pytest

from lfx_liam_bundle.graphrag.kg_store import (
    clear_index,
    ensure_kg_schema,
    load_index,
    load_subgraph,
    persist_index,
)
from lfx_liam_bundle.graphrag.local_search import local_search
from lfx_liam_bundle.graphrag.models import Entity, GraphIndex, Relationship, TextUnit
from lfx_liam_bundle.graphrag.vector_search import ann_search_entities, ensure_vector_indexes

pytestmark = pytest.mark.integration


def _sample_index() -> GraphIndex:
    return GraphIndex(
        text_units=[
            TextUnit(id="tu_langflow", text="Langflow 是低代码 AI 编排平台，可连接 AstraDB。"),
            TextUnit(id="tu_arango", text="ArangoDB 支持向量索引与 GraphRAG 存储。"),
            TextUnit(id="tu_noise", text="今天天气不错，适合散步。"),
        ],
        entities=[
            Entity(
                id="ent_langflow",
                title="Langflow",
                type="产品",
                description="低代码 AI 编排平台",
                text_unit_ids=["tu_langflow"],
                community_ids=["comm_0"],
                rank=3.0,
            ),
            Entity(
                id="ent_astradb",
                title="AstraDB",
                type="产品",
                description="向量数据库服务",
                text_unit_ids=["tu_langflow"],
                community_ids=["comm_0"],
                rank=2.0,
            ),
            Entity(
                id="ent_arango",
                title="ArangoDB",
                type="产品",
                description="多模型数据库，支持向量索引",
                text_unit_ids=["tu_arango"],
                community_ids=["comm_0"],
                rank=2.0,
            ),
            Entity(
                id="ent_weather",
                title="天气",
                type="概念",
                description="气象情况",
                text_unit_ids=["tu_noise"],
                community_ids=["comm_1"],
                rank=1.0,
            ),
        ],
        relationships=[
            Relationship(
                id="rel_1",
                source="Langflow",
                target="AstraDB",
                description="可对接",
                weight=2.0,
                text_unit_ids=["tu_langflow"],
            ),
            Relationship(
                id="rel_2",
                source="Langflow",
                target="ArangoDB",
                description="可存储",
                weight=2.0,
                text_unit_ids=["tu_arango"],
            ),
        ],
    )


@pytest.mark.arango
def test_arango_persist_ann_subgraph_local_search(arango_kb, embedding) -> None:
    ensure_kg_schema(arango_kb, create_if_missing=True)
    index = _sample_index()

    stats = persist_index(arango_kb, index, embedding, replace=True)
    assert stats["backend"] == "arangodb"
    assert stats.get("vector_ann") == "ready", stats
    assert "vector_indexes" in stats
    import time

    time.sleep(0.5)

    loaded = load_index(arango_kb)
    assert len(loaded.entities) == 4
    assert all(e.description_embedding for e in loaded.entities)
    assert len(loaded.relationships) >= 2

    # ANN：问 Langflow，应优先命中相关实体，而不是「天气」
    qvec = embedding.embed_query("Langflow 连接向量数据库")
    hits = ann_search_entities(arango_kb, qvec, top_k=3)
    assert hits, "ANN 未返回任何实体——请确认 Arango 已开 --vector-index 且索引训练成功"
    hit_ids = [i for i, _ in hits]
    assert "ent_weather" not in hit_ids[:1] or "ent_langflow" in hit_ids
    assert "ent_langflow" in hit_ids or "ent_astradb" in hit_ids or "ent_arango" in hit_ids

    # 子图：只围绕种子加载，不应拖入无关「天气」实体（若邻居扩展未触及）
    partial = load_subgraph(arango_kb, entity_ids=["ent_langflow"], include_neighbors=True)
    partial_ids = {e.id for e in partial.entities}
    assert "ent_langflow" in partial_ids
    assert "ent_astradb" in partial_ids or "ent_arango" in partial_ids
    # 天气不应作为邻居出现
    assert "ent_weather" not in partial_ids

    docs, text, meta = local_search(
        arango_kb,
        "Langflow 能连什么数据库",
        embedding,
        llm=None,
        answer_with_llm=False,
        top_k_entities=3,
        top_k_chunks=3,
    )
    assert docs
    assert meta.get("vector_ranking", "").startswith("ann:")
    assert meta.get("index_load") == "subgraph"
    assert "Langflow" in text or any("Langflow" in (d.metadata.get("title") or "") for d in docs)

    cleared = clear_index(arango_kb)
    assert cleared["cleared"] is True
    empty = load_index(arango_kb)
    assert not empty.entities
    assert not empty.text_units


@pytest.mark.arango
def test_arango_vector_index_requires_feature(arango_kb, embedding) -> None:
    """确保 ensure_vector_indexes 在真库上可创建 IVF/HNSW factory 索引。"""
    ensure_kg_schema(arango_kb, create_if_missing=True)
    index = _sample_index()
    persist_index(arango_kb, index, embedding, replace=True)
    import time

    time.sleep(0.5)
    dim = 8
    result = ensure_vector_indexes(
        arango_kb,
        dim=dim,
        entity_count=len(index.entities),
        chunk_count=len(index.text_units),
        report_count=0,
    )
    assert result["backend"] == "arangodb"
    ent_name = f"{arango_kb.collection_name}_entities"
    assert result["indexes"][ent_name]["ok"] is True
    assert "HNSW" in result["indexes"][ent_name]["factory"] or "IVF" in result["indexes"][ent_name]["factory"]

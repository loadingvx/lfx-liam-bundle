"""Astra 云 / 本地 Data API(HCD) 真库集成测试。

未配置环境变量时 skip（当前默认 compose 只保证 Arango；
Astra 需云凭证或自建 HCD，见 devops/env.integration.example）。
"""

from __future__ import annotations

import pytest

from lfx_liam_bundle.graphrag.kg_store import clear_index, ensure_kg_schema, load_index, persist_index
from lfx_liam_bundle.graphrag.local_search import local_search
from lfx_liam_bundle.graphrag.models import Entity, GraphIndex, TextUnit
from lfx_liam_bundle.graphrag.vector_search import ann_search_entities

pytestmark = [pytest.mark.integration, pytest.mark.astra]


def test_astra_or_hcd_persist_ann_local_search(astra_kb, embedding) -> None:
    ensure_kg_schema(astra_kb, create_if_missing=True)
    # 精简样本：Astra 向量集合重建成本更高
    index = GraphIndex(
        text_units=[
            TextUnit(id="tu1", text="Langflow connects to AstraDB for vector search."),
            TextUnit(id="tu2", text="Weather is sunny today."),
        ],
        entities=[
            Entity(
                id="e_langflow",
                title="Langflow",
                type="产品",
                description="AI orchestration",
                text_unit_ids=["tu1"],
                rank=3,
            ),
            Entity(
                id="e_astra",
                title="AstraDB",
                type="产品",
                description="Vector database",
                text_unit_ids=["tu1"],
                rank=2,
            ),
            Entity(
                id="e_weather",
                title="Weather",
                type="概念",
                description="Climate",
                text_unit_ids=["tu2"],
                rank=1,
            ),
        ],
    )
    stats = persist_index(astra_kb, index, embedding, replace=True)
    assert stats["backend"] == "astradb"
    assert stats.get("vector_ann") == "ready", stats
    import time

    time.sleep(0.5)

    loaded = load_index(astra_kb)
    assert len(loaded.entities) == 3
    assert all(e.description_embedding for e in loaded.entities)

    qvec = embedding.embed_query("Langflow AstraDB vector")
    hits = ann_search_entities(astra_kb, qvec, top_k=2)
    assert hits, "Astra/Data API `$vector` 检索未返回结果"
    hit_ids = [i for i, _ in hits]
    assert "e_langflow" in hit_ids or "e_astra" in hit_ids

    _docs, text, meta = local_search(
        astra_kb,
        "What database does Langflow use",
        embedding,
        llm=None,
        answer_with_llm=False,
        top_k_entities=2,
    )
    assert meta.get("vector_ranking", "").startswith("ann:")
    assert "Langflow" in text or "Astra" in text

    clear_index(astra_kb)
    empty = load_index(astra_kb)
    assert not empty.entities

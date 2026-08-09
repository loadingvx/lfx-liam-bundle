"""向量 ANN 辅助逻辑与 Local Search seed 路径单测。"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.local_search import build_local_context
from lfx_liam_bundle.graphrag.models import Entity, GraphIndex, TextUnit
from lfx_liam_bundle.graphrag.vector_search import (
    build_arango_factory,
    choose_n_lists,
    infer_embedding_dim,
)


class _FakeEmb(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_choose_n_lists_respects_doc_count() -> None:
    assert choose_n_lists(0) == 1
    assert choose_n_lists(1) == 1
    assert choose_n_lists(10) <= 10
    assert choose_n_lists(10, configured=100) == 10
    assert choose_n_lists(1000, configured=50) == 50


def test_build_arango_factory_rewrites_ivf() -> None:
    assert build_arango_factory(8, "IVF100_HNSW10,Flat", n_docs=100) == "IVF8_HNSW10,Flat"
    assert build_arango_factory(16, "", n_docs=100) == "IVF16_HNSW10,Flat"
    # 小样本禁用 HNSW，避免 Arango 3.12.4 Faiss 崩溃
    assert build_arango_factory(2, "IVF100_HNSW10,Flat", n_docs=3) == "IVF2,Flat"


def test_infer_embedding_dim() -> None:
    index = GraphIndex(
        entities=[
            Entity(id="e1", title="A", description_embedding=[0.1, 0.2, 0.3, 0.4])
        ]
    )
    assert infer_embedding_dim(index) == 4


def test_build_local_context_respects_ann_seed_ids() -> None:
    index = GraphIndex(
        text_units=[TextUnit(id="t1", text="hello", embedding=[1.0, 0.0, 0.0])],
        entities=[
            Entity(
                id="e_low",
                title="噪声",
                description="无关",
                description_embedding=[0.0, 1.0, 0.0],
                text_unit_ids=["t1"],
                rank=99,
            ),
            Entity(
                id="e_hit",
                title="目标",
                description="命中",
                description_embedding=[0.9, 0.1, 0.0],
                text_unit_ids=["t1"],
                rank=1,
            ),
        ],
    )
    # 若不看 seed，按余弦可能仍偏向某些向量；这里强制 ANN 种子只给 e_hit
    context, _docs, meta = build_local_context(
        index,
        "任意问题",
        _FakeEmb(),
        seed_entity_ids=["e_hit"],
        ranking_source="ann:astradb",
        query_vector=[1.0, 0.0, 0.0],
    )
    assert "目标" in context
    assert meta["vector_ranking"] == "ann:astradb"
    assert meta["entities"] == 1

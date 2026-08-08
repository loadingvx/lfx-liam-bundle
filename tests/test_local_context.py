"""Local Search 上下文装配单测（假 Embedding）。"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.local_search import build_local_context
from lfx_liam_bundle.graphrag.models import (
    CommunityReport,
    Entity,
    GraphIndex,
    Relationship,
    TextUnit,
)


class _FakeEmb(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 1.0, 0.0] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.0]


def test_build_local_context_includes_neighborhood() -> None:
    index = GraphIndex(
        text_units=[TextUnit(id="t1", text="Langflow 连接 AstraDB", embedding=[10.0, 1.0, 0.0])],
        entities=[
            Entity(
                id="e1",
                title="Langflow",
                type="产品",
                description="低代码平台",
                description_embedding=[8.0, 1.0, 0.0],
                text_unit_ids=["t1"],
                community_ids=["c0"],
                rank=3,
            ),
            Entity(
                id="e2",
                title="AstraDB",
                type="产品",
                description="向量数据库",
                description_embedding=[1.0, 0.0, 1.0],
                text_unit_ids=["t1"],
                community_ids=["c0"],
                rank=2,
            ),
        ],
        relationships=[
            Relationship(
                id="r1", source="Langflow", target="AstraDB", description="可对接", weight=2
            )
        ],
        community_reports=[
            CommunityReport(
                id="rep1",
                community_id="c0",
                level=0,
                title="平台社区",
                summary="围绕 Langflow",
                full_content="详细报告",
                rank=2,
            )
        ],
    )
    context, docs, meta = build_local_context(index, "Langflow 是什么", _FakeEmb())
    assert "相关实体" in context
    assert "关系" in context
    assert "原文片段" in context
    assert meta["entities"] >= 1
    assert docs

"""完整 GraphRAG 核心逻辑单测（不依赖真实 LLM/DB）。"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.communities import detect_hierarchical_communities
from lfx_liam_bundle.graphrag.community_reports import _parse_report
from lfx_liam_bundle.graphrag.extract_graph import merge_graph_primitives
from lfx_liam_bundle.graphrag.kg_store import _base_name
from lfx_liam_bundle.graphrag.models import (
    Entity,
    GraphIndex,
    Relationship,
    TextUnit,
    merge_graph_indexes,
)
from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


def test_search_modes_are_local_global() -> None:
    assert SEARCH_MODES == ["Local Search", "Global Search"]


def test_merge_graph_primitives_dedupes() -> None:
    extractions = [
        (
            "u1",
            [{"title": "Langflow", "type": "产品", "description": "低代码平台"}],
            [{"source": "Langflow", "target": "AstraDB", "description": "可对接", "weight": 1}],
        ),
        (
            "u2",
            [{"title": "Langflow", "type": "产品", "description": "可视化编排"}],
            [{"source": "Langflow", "target": "AstraDB", "description": "向量存储", "weight": 2}],
        ),
    ]
    entities, relationships = merge_graph_primitives(extractions, llm=None)
    assert len(entities) == 1
    assert "低代码" in entities[0].description or "可视化" in entities[0].description
    assert len(relationships) == 1
    assert relationships[0].weight == 3.0
    assert set(entities[0].text_unit_ids) == {"u1", "u2"}


def test_hierarchical_communities_and_ranks() -> None:
    entities = [
        Entity(id="e1", title="A", type="概念", description="a"),
        Entity(id="e2", title="B", type="概念", description="b"),
        Entity(id="e3", title="C", type="概念", description="c"),
        Entity(id="e4", title="D", type="概念", description="d"),
    ]
    relationships = [
        Relationship(id="r1", source="A", target="B", weight=2),
        Relationship(id="r2", source="B", target="C", weight=2),
        Relationship(id="r3", source="C", target="D", weight=1),
        Relationship(id="r4", source="A", target="C", weight=1),
    ]
    communities = detect_hierarchical_communities(
        entities, relationships, max_cluster_size=2, max_levels=3
    )
    assert communities
    assert any(c.level == 0 for c in communities)
    assert all(e.rank >= 0 for e in entities)
    assert any(e.community_ids for e in entities)


def test_parse_community_report() -> None:
    title, summary, full = _parse_report("标题：测试社区\n摘要：这是摘要\n报告：第一点\n第二点")
    assert title == "测试社区"
    assert "摘要" in summary or summary == "这是摘要"
    assert "第一点" in full


def test_merge_indexes_and_collection_base() -> None:
    a = GraphIndex(
        text_units=[TextUnit(id="t1", text="hello")],
        entities=[Entity(id="e1", title="X", description="old")],
        relationships=[Relationship(id="r1", source="X", target="Y", weight=1)],
    )
    b = GraphIndex(
        text_units=[TextUnit(id="t2", text="world")],
        entities=[Entity(id="e1", title="X", description="new", text_unit_ids=["t2"])],
        relationships=[Relationship(id="r1", source="X", target="Y", weight=2, description="rel")],
    )
    merged = merge_graph_indexes(a, b)
    assert len(merged.text_units) == 2
    assert len(merged.entities) == 1
    assert "t2" in merged.entities[0].text_unit_ids
    assert merged.relationships[0].weight == 3.0

    kb = GraphRAGKnowledgeBase(backend="astradb", name="n", collection_name="liam_graphrag_chunks")
    assert _base_name(kb) == "liam_graphrag"

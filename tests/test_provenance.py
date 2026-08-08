"""双向溯源 Entity↔TextUnit↔Document 单测。"""

from __future__ import annotations

import pytest

from lfx_liam_bundle.graphrag.models import (
    DocumentRecord,
    Entity,
    GraphIndex,
    Relationship,
    TextUnit,
)
from lfx_liam_bundle.graphrag.provenance import (
    document_to_graph,
    entity_to_sources,
    link_provenance,
    text_unit_to_graph,
)


def _sample_index() -> GraphIndex:
    return GraphIndex(
        documents=[DocumentRecord(id="doc1", title="手册", text="全文预览", text_unit_ids=["tu1"])],
        text_units=[
            TextUnit(id="tu1", text="Langflow 可以对接 AstraDB。", document_id="doc1"),
            TextUnit(id="tu2", text="无关片段。", document_id="doc1"),
        ],
        entities=[
            Entity(
                id="ent_lf",
                title="Langflow",
                type="产品",
                description="平台",
                text_unit_ids=["tu1"],
            ),
            Entity(
                id="ent_astra",
                title="AstraDB",
                type="产品",
                description="数据库",
                text_unit_ids=["tu1"],
            ),
        ],
        relationships=[
            Relationship(
                id="rel1",
                source="Langflow",
                target="AstraDB",
                description="可对接",
                text_unit_ids=["tu1"],
            )
        ],
    )


def test_link_provenance_bidirectional() -> None:
    index = _sample_index()
    stats = link_provenance(index)
    assert stats["entities_with_sources"] == 2
    assert stats["text_units_with_entities"] == 1
    tu1 = next(u for u in index.text_units if u.id == "tu1")
    assert set(tu1.entity_ids) == {"ent_lf", "ent_astra"}
    assert "rel1" in tu1.relationship_ids
    assert tu1.n_tokens and tu1.n_tokens > 0
    doc = index.documents[0]
    assert "tu1" in doc.text_unit_ids
    assert "tu2" in doc.text_unit_ids


def test_entity_to_sources_and_reverse() -> None:
    index = _sample_index()
    link_provenance(index)
    forward = entity_to_sources(index, "Langflow")
    assert forward["source_count"] == 1
    assert forward["sources"][0]["text_unit_id"] == "tu1"
    assert "AstraDB" in forward["sources"][0]["text"] or "Langflow" in forward["sources"][0]["text"]

    reverse = text_unit_to_graph(index, "tu1")
    titles = {e["title"] for e in reverse["entities"]}
    assert titles == {"Langflow", "AstraDB"}
    assert len(reverse["relationships"]) == 1

    doc_view = document_to_graph(index, "手册")
    assert doc_view["document"]["id"] == "doc1"
    assert len(doc_view["entities"]) == 2


def test_entity_missing_raises() -> None:
    index = _sample_index()
    link_provenance(index)
    with pytest.raises(ValueError, match="未找到实体"):
        entity_to_sources(index, "不存在的实体")

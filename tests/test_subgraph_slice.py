"""子图切片逻辑单测（不连真实 DB）。"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.kg_store import _slice_index_for_entities
from lfx_liam_bundle.graphrag.models import (
    CommunityReport,
    Entity,
    GraphIndex,
    Relationship,
    TextUnit,
)


def test_slice_index_keeps_neighborhood() -> None:
    index = GraphIndex(
        text_units=[
            TextUnit(id="t1", text="a"),
            TextUnit(id="t2", text="b"),
            TextUnit(id="t9", text="noise"),
        ],
        entities=[
            Entity(
                id="e1",
                title="Alpha",
                text_unit_ids=["t1"],
                community_ids=["c0"],
            ),
            Entity(
                id="e2",
                title="Beta",
                text_unit_ids=["t2"],
                community_ids=["c0"],
            ),
            Entity(id="e9", title="Noise", text_unit_ids=["t9"], community_ids=["c9"]),
        ],
        relationships=[
            Relationship(id="r1", source="Alpha", target="Beta", description="link"),
            Relationship(id="r9", source="Noise", target="Noise", description="x"),
        ],
        community_reports=[
            CommunityReport(
                id="rep0",
                community_id="c0",
                level=0,
                title="c0",
                summary="s",
                full_content="f",
            ),
            CommunityReport(
                id="rep9",
                community_id="c9",
                level=0,
                title="c9",
                summary="s",
                full_content="f",
            ),
        ],
    )
    partial = _slice_index_for_entities(index, ["e1"], include_neighbors=True)
    ids = {e.id for e in partial.entities}
    assert "e1" in ids
    assert "e2" in ids
    assert "e9" not in ids
    assert {u.id for u in partial.text_units} == {"t1", "t2"}
    assert {r.id for r in partial.community_reports} == {"rep0"}

"""内置切块与 token 预算单测。"""

from __future__ import annotations

from langchain_core.documents import Document

from lfx_liam_bundle.graphrag.chunking import compose_text_units
from lfx_liam_bundle.graphrag.tokens import allocate_budget, count_tokens, join_under_budget


def test_compose_text_units_chunks_long_doc() -> None:
    long = ("Langflow GraphRAG 测试段落。" * 80) + (" More English tokens." * 40)
    units, docs, stats = compose_text_units(
        [Document(page_content=long, metadata={"source": "demo.md"}, id="d1")],
        chunk_size=64,
        chunk_overlap=8,
        chunk_enabled=True,
    )
    assert stats["chunk_enabled"] is True
    assert len(docs) == 1
    assert len(units) >= 2
    assert docs[0].text_unit_ids
    assert all(u.document_id == docs[0].id for u in units)


def test_token_budget_allocation_and_pack() -> None:
    budget = allocate_budget(1000, text_unit_prop=0.5, community_prop=0.25)
    assert budget["text_units"] == 500
    assert budget["community_reports"] == 250
    assert budget["graph"] == 250
    packed = join_under_budget(["短句一", "短句二" * 50], max_tokens=20)
    assert packed
    assert count_tokens(packed) <= 25

"""检索辅助函数单测。"""

from __future__ import annotations

import pytest

from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES, traversal_strategy_names


def test_traversal_strategy_names_are_search_modes() -> None:
    names = traversal_strategy_names()
    assert names == SEARCH_MODES
    assert "Local Search" in names
    assert "Global Search" in names


def test_evaluate_edge_definition_id() -> None:
    pytest.importorskip("graph_retriever")
    from lfx_liam_bundle.graphrag.edges import evaluate_edge_definition

    edge = evaluate_edge_definition("mentions,Id()")
    assert edge[0] == "mentions"
    assert edge[1].__class__.__name__ == "Id"

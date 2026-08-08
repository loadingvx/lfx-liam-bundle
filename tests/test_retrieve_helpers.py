"""检索辅助函数单测。"""

from __future__ import annotations

import pytest

from lfx_liam_bundle.graphrag.retrieve import traversal_strategy_names

graph_retriever = pytest.importorskip("graph_retriever")


def test_traversal_strategy_names_non_empty() -> None:
    names = traversal_strategy_names()
    assert isinstance(names, list)
    assert names


def test_evaluate_edge_definition_id() -> None:
    from lfx_liam_bundle.graphrag.edges import evaluate_edge_definition

    edge = evaluate_edge_definition("mentions,Id()")
    assert edge[0] == "mentions"
    assert edge[1].__class__.__name__ == "Id"

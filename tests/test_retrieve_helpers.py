"""检索模式单测。"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES


def test_search_modes() -> None:
    assert SEARCH_MODES == ["Local Search", "Global Search"]

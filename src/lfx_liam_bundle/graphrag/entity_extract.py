"""实体/关系抽取入口（转发至 extract_graph）。"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.extract_graph import (  # noqa: F401
    DEFAULT_ENTITY_TYPES,
    extract_from_text_unit,
    extract_graph_from_units,
    merge_graph_primitives,
)

__all__ = [
    "DEFAULT_ENTITY_TYPES",
    "extract_from_text_unit",
    "extract_graph_from_units",
    "merge_graph_primitives",
]

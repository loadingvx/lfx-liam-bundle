"""lfx-liam-bundle: Liam GraphRAG Langflow Extension.

以知识库实例为边界，提供建库（入库/索引/建图）、检索与维护全流程组件。
运行时由 Langflow 通过 ``langflow.extensions`` entry-point 发现
``extension.json`` 并注册 bundle ``liam``。
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from lfx_liam_bundle.components.liam.kb_build import GraphRAGKBBuildComponent
from lfx_liam_bundle.components.liam.kb_instance import GraphRAGKBInstanceComponent
from lfx_liam_bundle.components.liam.kb_maintain import GraphRAGKBMaintainComponent
from lfx_liam_bundle.components.liam.kb_provenance import GraphRAGKBProvenanceComponent
from lfx_liam_bundle.components.liam.kb_retrieve import GraphRAGKBRetrieveComponent

try:
    __version__ = version("lfx-liam-bundle")
except PackageNotFoundError:  # pragma: no cover - 未安装/未 editable 时的兜底
    __version__ = "0.0.0+local"

__all__ = [
    "GraphRAGKBBuildComponent",
    "GraphRAGKBInstanceComponent",
    "GraphRAGKBMaintainComponent",
    "GraphRAGKBProvenanceComponent",
    "GraphRAGKBRetrieveComponent",
    "__version__",
]

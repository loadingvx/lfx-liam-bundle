"""lfx-liam-bundle：Liam 的 Langflow 扩展工具包。

通过 ``langflow.extensions`` entry-point 发现 ``extension.json``，
注册 bundle ``liam``。当前导出 GraphRAG 相关控件；后续其它能力也应挂在同一 bundle 下。
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

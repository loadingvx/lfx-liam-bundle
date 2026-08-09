"""lfx-liam-bundle: Liam's Langflow extension toolkit.

Discovered via the ``langflow.extensions`` entry-point and ``extension.json``,
registering bundle ``liam``. Ships GraphRAG components today; further tools
should join the same bundle.
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
except PackageNotFoundError:  # pragma: no cover - fallback when not installed/editable
    __version__ = "0.0.0+local"

__all__ = [
    "GraphRAGKBBuildComponent",
    "GraphRAGKBInstanceComponent",
    "GraphRAGKBMaintainComponent",
    "GraphRAGKBProvenanceComponent",
    "GraphRAGKBRetrieveComponent",
    "__version__",
]

"""Build side: GraphRAG knowledge-base instance (create / connect)."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import ensure_kg_schema, load_index
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

# Fields shown only for AstraDB / Data API
_ASTRA_FIELDS = (
    "api_endpoint",
    "token",
    "data_api_environment",
    "keyspace",
)
# HCD credentials: only when Astra backend + environment == hcd
_HCD_FIELDS = (
    "data_api_username",
    "data_api_password",
)
# Fields shown only for ArangoDB
_ARANGO_FIELDS = (
    "arango_url",
    "arango_username",
    "arango_password",
    "arango_database",
    "graph_name",
    "vector_index_factory",
)


class GraphRAGKBInstanceComponent(Component):
    display_name = "GraphRAG Knowledge Base"
    description = (
        "Create or connect a GraphRAG knowledge-base instance (AstraDB / ArangoDB). "
        "Build and retrieve flows share this instance. "
        "Connection fields update when you switch the storage backend."
    )
    name = "LiamGraphRAGKB"
    icon = "Database"

    inputs = [
        DropdownInput(
            name="backend",
            display_name="Storage backend",
            options=["AstraDB", "ArangoDB"],
            value="AstraDB",
            info="Choose one backend. Only that backend's connection fields are shown.",
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="kb_name",
            display_name="Knowledge base name",
            value="default",
            info="Display name used in the UI.",
            required=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Collection prefix",
            value="liam_graphrag",
            info=(
                "Storage prefix. The system creates collections such as "
                "`{prefix}_chunks/_entities/_relationships/_communities/_reports`. "
                "Do not append `_chunks` yourself."
            ),
            required=True,
        ),
        BoolInput(
            name="create_if_missing",
            display_name="Create if missing",
            value=True,
            info="Create target collections when they do not exist.",
        ),
        # --- AstraDB / Data API (hidden when ArangoDB is selected) ---
        MessageTextInput(
            name="api_endpoint",
            display_name="Astra / Data API Endpoint",
            info="Cloud Astra endpoint, or local HCD Data API (e.g. http://localhost:8181).",
            dynamic=True,
            show=True,
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra Token",
            info="Required for cloud Astra (environment=astra). Local HCD uses username/password instead.",
            dynamic=True,
            show=True,
        ),
        DropdownInput(
            name="data_api_environment",
            display_name="Data API environment",
            options=["astra", "hcd"],
            value="astra",
            advanced=True,
            info="astra = cloud AstraDB (Token); hcd = local/self-hosted Data API (username/password).",
            dynamic=True,
            show=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="data_api_username",
            display_name="Data API username",
            value="",
            advanced=True,
            info="Required for hcd only (e.g. cassandra).",
            dynamic=True,
            show=False,
        ),
        SecretStrInput(
            name="data_api_password",
            display_name="Data API password",
            advanced=True,
            info="Required for hcd only.",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="keyspace",
            display_name="Astra / Data API Keyspace",
            value="default_keyspace",
            advanced=True,
            dynamic=True,
            show=True,
        ),
        # --- ArangoDB (hidden when AstraDB is selected) ---
        MessageTextInput(
            name="arango_url",
            display_name="ArangoDB URL",
            value="http://localhost:8529",
            info="ArangoDB HTTP API URL (e.g. http://localhost:8529).",
            dynamic=True,
            show=False,
            required=False,
        ),
        StrInput(
            name="arango_username",
            display_name="ArangoDB username",
            value="root",
            dynamic=True,
            show=False,
        ),
        SecretStrInput(
            name="arango_password",
            display_name="ArangoDB password",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="arango_database",
            display_name="ArangoDB database",
            value="_system",
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="graph_name",
            display_name="Arango graph name",
            value="",
            advanced=True,
            info="Leave empty to use `{prefix}_kg_graph` automatically.",
            dynamic=True,
            show=False,
        ),
        # --- Shared vector options ---
        BoolInput(
            name="use_vector_index",
            display_name="Enable vector ANN retrieval",
            value=True,
            info=(
                "On by default. Astra uses `$vector` ANN; Arango creates Faiss vector indexes "
                "and uses approximate AQL search. On failure, exact cosine fallback is used by "
                "default so retrieve does not hard-fail."
            ),
        ),
        BoolInput(
            name="ann_fallback_exact",
            display_name="Fall back to exact cosine if ANN fails",
            value=True,
            advanced=True,
            info="If off, vector index/search failures raise immediately (useful for debugging).",
        ),
        StrInput(
            name="vector_index_factory",
            display_name="Arango vector index factory",
            value="IVF100_HNSW10,Flat",
            advanced=True,
            info=(
                "Arango only. Faiss factory string (default IVF+HNSW). "
                "IVF list count is auto-adjusted for small corpora."
            ),
            dynamic=True,
            show=False,
        ),
        StrInput(
            name="metric",
            display_name="Vector similarity",
            value="cosine",
            advanced=True,
            info="cosine (recommended) / l2 / innerProduct (Arango) or the Astra equivalent.",
        ),
    ]

    outputs = [
        Output(display_name="KB instance", name="kb_instance", method="build_kb"),
    ]

    @staticmethod
    def _cfg_value(build_config: dict, name: str, default: Any = None) -> Any:
        field = build_config.get(name) or {}
        if isinstance(field, dict):
            return field.get("value", default)
        return default

    @staticmethod
    def _set_show(build_config: dict, names: tuple[str, ...], *, show: bool) -> None:
        for name in names:
            if name in build_config and isinstance(build_config[name], dict):
                build_config[name]["show"] = show

    @staticmethod
    def _set_required(build_config: dict, name: str, *, required: bool) -> None:
        if name in build_config and isinstance(build_config[name], dict):
            build_config[name]["required"] = required

    def _apply_field_visibility(
        self,
        build_config: dict,
        *,
        backend: str | None,
        data_api_environment: str | None,
    ) -> dict:
        is_astra = (backend or "AstraDB") == "AstraDB"
        is_arango = not is_astra
        env = (data_api_environment or "astra").strip().lower()
        show_hcd = is_astra and env == "hcd"

        self._set_show(build_config, _ASTRA_FIELDS, show=is_astra)
        self._set_show(build_config, _HCD_FIELDS, show=show_hcd)
        self._set_show(build_config, _ARANGO_FIELDS, show=is_arango)

        # Required only for the active backend's primary connection field
        self._set_required(build_config, "api_endpoint", required=is_astra)
        self._set_required(build_config, "arango_url", required=is_arango)
        self._set_required(build_config, "token", required=is_astra and env == "astra")
        self._set_required(build_config, "data_api_username", required=show_hcd)
        self._set_required(build_config, "data_api_password", required=show_hcd)

        return build_config

    def update_build_config(
        self,
        build_config: dict,
        field_value: Any,
        field_name: str | None = None,
    ) -> dict:
        """Show only fields that belong to the selected backend (and HCD when needed)."""
        backend = self._cfg_value(build_config, "backend", "AstraDB")
        data_api_environment = self._cfg_value(build_config, "data_api_environment", "astra")

        if field_name == "backend":
            backend = field_value or backend
            if field_name in build_config and isinstance(build_config[field_name], dict):
                build_config[field_name]["value"] = field_value
        elif field_name == "data_api_environment":
            data_api_environment = field_value or data_api_environment
            if field_name in build_config and isinstance(build_config[field_name], dict):
                build_config[field_name]["value"] = field_value
        elif field_name is None:
            # Initial template build: honor defaults already on the inputs
            pass

        return self._apply_field_visibility(
            build_config,
            backend=str(backend or "AstraDB"),
            data_api_environment=str(data_api_environment or "astra"),
        )

    def build_kb(self) -> Data:
        backend_label = (self.backend or "AstraDB").strip()
        if backend_label not in {"AstraDB", "ArangoDB"}:
            msg = "Storage backend must be AstraDB or ArangoDB."
            raise ValueError(msg)

        backend = "astradb" if backend_label == "AstraDB" else "arangodb"
        data_api_environment = (
            "hcd" if (self.data_api_environment or "astra") == "hcd" else "astra"
        )

        if backend == "astradb":
            endpoint = (self.api_endpoint or "").strip()
            if not endpoint:
                msg = (
                    "AstraDB is selected: fill Astra / Data API Endpoint "
                    "(cloud Astra URL or local HCD, e.g. http://localhost:8181)."
                )
                raise ValueError(msg)
            if data_api_environment == "astra" and not (self.token or "").strip():
                msg = (
                    "AstraDB cloud (environment=astra) requires Astra Token. "
                    "For local HCD, set Data API environment to hcd and use username/password."
                )
                raise ValueError(msg)
            if data_api_environment == "hcd" and (
                not (self.data_api_username or "").strip() or not (self.data_api_password or "")
            ):
                msg = (
                    "Data API environment is hcd: fill Data API username and Data API password "
                    "(shown under Advanced)."
                )
                raise ValueError(msg)
        else:
            if not (self.arango_url or "").strip():
                msg = "ArangoDB is selected: fill ArangoDB URL (e.g. http://localhost:8529)."
                raise ValueError(msg)

        kb = GraphRAGKnowledgeBase(
            backend=backend,  # type: ignore[arg-type]
            name=(self.kb_name or "default").strip(),
            collection_name=(self.collection_name or "").strip(),
            api_endpoint=(self.api_endpoint or "").strip() if backend == "astradb" else "",
            token=(self.token or "") if backend == "astradb" else "",
            keyspace=(self.keyspace or "default_keyspace").strip()
            if backend == "astradb"
            else "default_keyspace",
            data_api_environment=data_api_environment,  # type: ignore[arg-type]
            data_api_username=(self.data_api_username or "").strip()
            if backend == "astradb"
            else "",
            data_api_password=(self.data_api_password or "") if backend == "astradb" else "",
            arango_url=(self.arango_url or "").strip() if backend == "arangodb" else "",
            arango_username=(self.arango_username or "root").strip()
            if backend == "arangodb"
            else "root",
            arango_password=(self.arango_password or "") if backend == "arangodb" else "",
            arango_database=(self.arango_database or "_system").strip()
            if backend == "arangodb"
            else "_system",
            graph_name=(self.graph_name or "").strip() if backend == "arangodb" else "",
            use_vector_index=bool(self.use_vector_index),
            ann_fallback_exact=bool(self.ann_fallback_exact),
            vector_index_factory=(self.vector_index_factory or "IVF100_HNSW10,Flat").strip()
            if backend == "arangodb"
            else "IVF100_HNSW10,Flat",
            metric=(self.metric or "cosine").strip() or "cosine",
        )
        try:
            ensure_kg_schema(kb, create_if_missing=bool(self.create_if_missing))
            try:
                index = load_index(kb)
                kb.document_count = len(index.text_units)
                if index.entities or index.text_units:
                    kb.status = "ready"
                    ann = (
                        "vector ANN=on (Astra `$vector` / Arango Faiss)"
                        if kb.use_vector_index
                        else "vector ANN=off (exact cosine)"
                    )
                    kb.message = (
                        f"Connected GraphRAG KB 「{kb.name}」[{kb.backend}]: "
                        f"text units {len(index.text_units)}, entities {len(index.entities)}, "
                        f"relationships {len(index.relationships)}, communities {len(index.communities)}, "
                        f"reports {len(index.community_reports)}; {ann}."
                    )
                else:
                    kb.status = "empty"
                    kb.message = (
                        f"Connected GraphRAG KB 「{kb.name}」 with no graph yet. "
                        "Run GraphRAG Index Builder next."
                    )
            except Exception:
                kb.status = "empty"
                kb.message = (
                    f"Initialized GraphRAG storage skeleton 「{kb.collection_name}」. "
                    "Ready for indexing."
                )
        except Exception as e:
            kb.status = "error"
            kb.message = f"Failed to connect GraphRAG KB: {e}"
            self.status = kb.message
            raise ValueError(kb.message) from e

        self.status = kb.message
        self.log(str(kb.public_summary()))
        return kb.to_data()

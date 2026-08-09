"""Build side: GraphRAG knowledge-base instance (create / connect)."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import ensure_kg_schema, load_index
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBInstanceComponent(Component):
    display_name = "GraphRAG Knowledge Base"
    description = (
        "Create or connect a GraphRAG knowledge-base instance (AstraDB / ArangoDB). "
        "Build and retrieve flows share this instance."
    )
    name = "LiamGraphRAGKB"
    icon = "Database"

    inputs = [
        DropdownInput(
            name="backend",
            display_name="Storage backend",
            options=["AstraDB", "ArangoDB"],
            value="AstraDB",
            info="Supports AstraDB and ArangoDB only.",
            required=True,
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
        MessageTextInput(
            name="api_endpoint",
            display_name="Astra / Data API Endpoint",
            info="Cloud Astra endpoint, or local HCD Data API (e.g. http://localhost:8181).",
        ),
        SecretStrInput(
            name="token",
            display_name="Astra Token",
            info="Required for cloud Astra. Local HCD uses username/password below.",
        ),
        DropdownInput(
            name="data_api_environment",
            display_name="Data API environment",
            options=["astra", "hcd"],
            value="astra",
            advanced=True,
            info="astra = cloud AstraDB; hcd = local/self-hosted Data API (username/password).",
        ),
        StrInput(
            name="data_api_username",
            display_name="Data API username",
            value="",
            advanced=True,
            info="Required for hcd only (e.g. cassandra).",
        ),
        SecretStrInput(
            name="data_api_password",
            display_name="Data API password",
            advanced=True,
            info="Required for hcd only.",
        ),
        StrInput(
            name="keyspace",
            display_name="Astra / Data API Keyspace",
            value="default_keyspace",
            advanced=True,
        ),
        MessageTextInput(
            name="arango_url",
            display_name="ArangoDB URL",
            value="http://localhost:8529",
            info="Required for ArangoDB.",
        ),
        StrInput(
            name="arango_username",
            display_name="ArangoDB username",
            value="root",
        ),
        SecretStrInput(
            name="arango_password",
            display_name="ArangoDB password",
        ),
        StrInput(
            name="arango_database",
            display_name="ArangoDB database",
            value="_system",
        ),
        StrInput(
            name="graph_name",
            display_name="Arango graph name",
            value="",
            advanced=True,
            info="Leave empty to use `{prefix}_kg_graph` automatically.",
        ),
        BoolInput(
            name="use_vector_index",
            display_name="Enable vector ANN retrieval",
            value=True,
            info=(
                "On by default. Astra uses `$vector` ANN; Arango creates Faiss vector indexes "
                "(IVF+HNSW factory supported) and uses approximate AQL search. "
                "On failure, exact cosine fallback is used by default so retrieve does not hard-fail."
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

    def build_kb(self) -> Data:
        backend = "astradb" if self.backend == "AstraDB" else "arangodb"
        kb = GraphRAGKnowledgeBase(
            backend=backend,  # type: ignore[arg-type]
            name=(self.kb_name or "default").strip(),
            collection_name=(self.collection_name or "").strip(),
            api_endpoint=(self.api_endpoint or "").strip(),
            token=self.token or "",
            keyspace=(self.keyspace or "default_keyspace").strip(),
            data_api_environment=(  # type: ignore[arg-type]
                "hcd" if (self.data_api_environment or "astra") == "hcd" else "astra"
            ),
            data_api_username=(self.data_api_username or "").strip(),
            data_api_password=self.data_api_password or "",
            arango_url=(self.arango_url or "").strip(),
            arango_username=(self.arango_username or "root").strip(),
            arango_password=self.arango_password or "",
            arango_database=(self.arango_database or "_system").strip(),
            graph_name=(self.graph_name or "").strip(),
            use_vector_index=bool(self.use_vector_index),
            ann_fallback_exact=bool(self.ann_fallback_exact),
            vector_index_factory=(self.vector_index_factory or "IVF100_HNSW10,Flat").strip(),
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

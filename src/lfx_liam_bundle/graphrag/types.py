"""GraphRAG knowledge-base instance protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from lfx.schema.data import Data

KB_MARKER = "_liam_graphrag_kb"
Backend = Literal["astradb", "arangodb"]
Status = Literal["ready", "empty", "error"]


@dataclass
class GraphRAGKnowledgeBase:
    """Shared KB handle for indexing and retrieve flows."""

    backend: Backend
    name: str
    collection_name: str
    status: Status = "empty"
    message: str = "Knowledge base connected; not indexed yet."
    document_count: int = 0
    # Astra / local Data API (HCD)
    api_endpoint: str = ""
    token: str = ""
    keyspace: str = "default_keyspace"
    # astra = cloud AstraDB; hcd = local/self-hosted Data API (username/password)
    data_api_environment: Literal["astra", "hcd"] = "astra"
    data_api_username: str = ""
    data_api_password: str = ""
    # Arango
    arango_url: str = ""
    arango_username: str = "root"
    arango_password: str = ""
    arango_database: str = "_system"
    graph_name: str = ""
    # Vector ANN
    embedding_dim: int | None = None
    metric: str = "cosine"
    use_vector_index: bool = True
    # Arango Faiss factory template; IVF list count shrinks for small corpora
    vector_index_factory: str = "IVF100_HNSW10,Flat"
    vector_n_lists: int | None = None
    # Fall back to in-process exact cosine when ANN fails (recommended)
    ann_fallback_exact: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload[KB_MARKER] = True
        return payload

    def to_data(self) -> Data:
        text = (
            f"KB 「{self.name}」[{self.backend}] "
            f"prefix={self.collection_name} status={self.status} docs={self.document_count}"
        )
        return Data(text=text, data=self.to_dict())

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GraphRAGKnowledgeBase:
        data = dict(raw)
        data.pop(KB_MARKER, None)
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(**filtered)

    @classmethod
    def from_data(cls, value: Any) -> GraphRAGKnowledgeBase:
        if isinstance(value, cls):
            return value
        if isinstance(value, Data):
            payload = value.data if isinstance(value.data, dict) else {}
            if not payload.get(KB_MARKER):
                msg = (
                    "Input is not a valid GraphRAG KB instance. "
                    "Connect the GraphRAG Knowledge Base component first."
                )
                raise ValueError(msg)
            return cls.from_dict(payload)
        if isinstance(value, dict) and value.get(KB_MARKER):
            return cls.from_dict(value)
        msg = (
            "No KB instance received. Connect the output of GraphRAG Knowledge Base "
            "or GraphRAG Index Builder to this component."
        )
        raise ValueError(msg)

    def public_summary(self) -> dict[str, Any]:
        """Status/log summary without secrets."""
        return {
            "backend": self.backend,
            "name": self.name,
            "collection_name": self.collection_name,
            "status": self.status,
            "message": self.message,
            "document_count": self.document_count,
            "keyspace": self.keyspace if self.backend == "astradb" else None,
            "arango_database": self.arango_database if self.backend == "arangodb" else None,
            "api_endpoint": self.api_endpoint if self.backend == "astradb" else None,
            "arango_url": self.arango_url if self.backend == "arangodb" else None,
            "use_vector_index": self.use_vector_index,
            "embedding_dim": self.embedding_dim,
            "metric": self.metric,
            "vector_index_factory": self.vector_index_factory
            if self.backend == "arangodb"
            else None,
        }

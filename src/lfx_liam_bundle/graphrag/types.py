"""GraphRAG 知识库实例协议。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from lfx.schema.data import Data

KB_MARKER = "_liam_graphrag_kb"
Backend = Literal["astradb", "arangodb"]
Status = Literal["ready", "empty", "error"]


@dataclass
class GraphRAGKnowledgeBase:
    """建库侧与检索侧共享的知识库实例句柄。"""

    backend: Backend
    name: str
    collection_name: str
    status: Status = "empty"
    message: str = "知识库已连接，尚未入库。"
    document_count: int = 0
    # Astra / 本地 Data API (HCD)
    api_endpoint: str = ""
    token: str = ""
    keyspace: str = "default_keyspace"
    # astra=云上 AstraDB；hcd=本地/自建 Data API（用户名密码）
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
    # Arango Faiss factory 模板；实际 IVF 基数会按文档数自动收缩
    vector_index_factory: str = "IVF100_HNSW10,Flat"
    vector_n_lists: int | None = None
    # ANN 失败时是否回退进程内精确余弦（建议保持开启，避免检索直接报错）
    ann_fallback_exact: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload[KB_MARKER] = True
        return payload

    def to_data(self) -> Data:
        text = (
            f"知识库「{self.name}」[{self.backend}] "
            f"集合={self.collection_name} 状态={self.status} 文档数={self.document_count}"
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
                msg = "输入不是有效的 GraphRAG 知识库实例。请先连接「GraphRAG 知识库」组件。"
                raise ValueError(msg)
            return cls.from_dict(payload)
        if isinstance(value, dict) and value.get(KB_MARKER):
            return cls.from_dict(value)
        msg = "未收到知识库实例。请将「GraphRAG 知识库」或「入库建图」的输出连接到本组件。"
        raise ValueError(msg)

    def public_summary(self) -> dict[str, Any]:
        """日志/状态用摘要（不含密钥）。"""
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

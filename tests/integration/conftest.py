"""真库集成测试 fixtures。"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator

import pytest
from langchain_core.embeddings import Embeddings

from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class DeterministicEmbeddings(Embeddings):
    """固定维度、可复现的假 Embedding（仍走真实 DB 向量索引/查询路径）。"""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        # 简单哈希展开为 dim 维，保证相同文本相同向量
        seed = sum(ord(c) for c in (text or "")) + len(text or "")
        out = []
        x = float(seed % 997) + 1.0
        for i in range(self.dim):
            x = (x * 1.6180339887 + i * 0.37) % 1.0
            out.append(x * 2.0 - 1.0)
        # L2 归一化，便于 cosine
        norm = sum(v * v for v in out) ** 0.5 or 1.0
        return [v / norm for v in out]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def arango_available() -> bool:
    url = _env("LFX_LIAM_ARANGO_URL", "http://127.0.0.1:18529")
    try:
        from arango import ArangoClient

        client = ArangoClient(hosts=url)
        db = client.db(
            "_system",
            username=_env("LFX_LIAM_ARANGO_USERNAME", "root"),
            password=_env("LFX_LIAM_ARANGO_PASSWORD", "liamtest"),
        )
        db.version()
        return True
    except Exception:
        return False


def astra_cloud_available() -> bool:
    return bool(_env("LFX_LIAM_ASTRA_API_ENDPOINT") and _env("LFX_LIAM_ASTRA_TOKEN"))


def data_api_hcd_available() -> bool:
    return bool(
        _env("LFX_LIAM_DATA_API_URL")
        and _env("LFX_LIAM_DATA_API_USERNAME")
        and _env("LFX_LIAM_DATA_API_PASSWORD")
    )


@pytest.fixture(scope="session")
def embedding() -> DeterministicEmbeddings:
    return DeterministicEmbeddings(dim=8)


@pytest.fixture
def unique_prefix() -> str:
    return f"it_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def arango_kb(unique_prefix: str) -> Iterator[GraphRAGKnowledgeBase]:
    if not arango_available():
        pytest.skip(
            "ArangoDB 不可用。请先执行 ./devops/db-up.sh "
            f"（当前 LFX_LIAM_ARANGO_URL={_env('LFX_LIAM_ARANGO_URL', 'http://127.0.0.1:18529')}）"
        )
    kb = GraphRAGKnowledgeBase(
        backend="arangodb",
        name="integration-arango",
        collection_name=unique_prefix,
        arango_url=_env("LFX_LIAM_ARANGO_URL", "http://127.0.0.1:18529"),
        arango_username=_env("LFX_LIAM_ARANGO_USERNAME", "root"),
        arango_password=_env("LFX_LIAM_ARANGO_PASSWORD", "liamtest"),
        arango_database=_env("LFX_LIAM_ARANGO_DATABASE", "_system"),
        use_vector_index=True,
        ann_fallback_exact=False,  # 集成测试要求 ANN 必须成功，不允许静默回退
        metric="cosine",
        vector_index_factory="IVF100_HNSW10,Flat",
    )
    yield kb
    # 清理
    try:
        from lfx_liam_bundle.graphrag.kg_store import clear_index

        clear_index(kb)
    except Exception:
        pass


@pytest.fixture
def astra_kb(unique_prefix: str) -> Iterator[GraphRAGKnowledgeBase]:
    if astra_cloud_available():
        kb = GraphRAGKnowledgeBase(
            backend="astradb",
            name="integration-astra",
            collection_name=unique_prefix,
            api_endpoint=_env("LFX_LIAM_ASTRA_API_ENDPOINT"),
            token=_env("LFX_LIAM_ASTRA_TOKEN"),
            keyspace=_env("LFX_LIAM_ASTRA_KEYSPACE", "default_keyspace"),
            data_api_environment="astra",
            use_vector_index=True,
            ann_fallback_exact=False,
            metric="cosine",
        )
    elif data_api_hcd_available():
        kb = GraphRAGKnowledgeBase(
            backend="astradb",
            name="integration-hcd",
            collection_name=unique_prefix,
            api_endpoint=_env("LFX_LIAM_DATA_API_URL"),
            keyspace=_env("LFX_LIAM_DATA_API_KEYSPACE", "default_keyspace"),
            data_api_environment="hcd",
            data_api_username=_env("LFX_LIAM_DATA_API_USERNAME"),
            data_api_password=_env("LFX_LIAM_DATA_API_PASSWORD"),
            use_vector_index=True,
            ann_fallback_exact=False,
            metric="cosine",
        )
    else:
        pytest.skip(
            "Astra/Data API 未配置。请设置 LFX_LIAM_ASTRA_API_ENDPOINT+TOKEN，"
            "或 LFX_LIAM_DATA_API_URL+USERNAME+PASSWORD（见 devops/env.integration.example）"
        )
    yield kb
    try:
        from lfx_liam_bundle.graphrag.kg_store import clear_index

        clear_index(kb)
    except Exception:
        pass


def wait_brief() -> None:
    """给索引训练一点时间（小库通常瞬时，留缓冲）。"""
    time.sleep(0.5)

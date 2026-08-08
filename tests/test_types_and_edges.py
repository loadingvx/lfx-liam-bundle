"""KB 协议与文档规范化单测。"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.edges import coerce_documents, stable_doc_id, weak_keywords_from_text
from lfx_liam_bundle.graphrag.types import KB_MARKER, GraphRAGKnowledgeBase


def test_kb_roundtrip_data() -> None:
    kb = GraphRAGKnowledgeBase(
        backend="astradb",
        name="demo",
        collection_name="c1",
        api_endpoint="https://example.com",
        token="secret",
        status="ready",
        message="ok",
        document_count=3,
    )
    data = kb.to_data()
    assert data.data[KB_MARKER] is True
    restored = GraphRAGKnowledgeBase.from_data(data)
    assert restored.name == "demo"
    assert restored.backend == "astradb"
    assert restored.document_count == 3
    assert "token" not in restored.public_summary()


def test_from_data_rejects_plain_data() -> None:
    with pytest.raises(ValueError, match="知识库实例"):
        GraphRAGKnowledgeBase.from_data(Data(text="x", data={"foo": 1}))


def test_from_dict_ignores_legacy_edge_fields() -> None:
    kb = GraphRAGKnowledgeBase.from_dict(
        {
            KB_MARKER: True,
            "backend": "astradb",
            "name": "n",
            "collection_name": "c",
            "edge_definition": "entities,entities",
            "edge_fields": ["entities"],
        }
    )
    assert kb.name == "n"
    assert "edge_definition" not in kb.__dataclass_fields__
    assert "edge_fields" not in kb.__dataclass_fields__


def test_coerce_documents() -> None:
    docs = coerce_documents(
        [
            Data(text="你好世界 GraphRAG", data={"source": "a.md"}),
            Document(page_content="第二段", metadata={"doc_id": "d2"}),
            "   ",
        ]
    )
    assert len(docs) == 2
    assert docs[0].metadata["doc_id"]
    assert docs[1].id == "d2"


def test_stable_doc_id_and_keywords() -> None:
    a = stable_doc_id("same text")
    b = stable_doc_id("same text")
    assert a == b
    kws = weak_keywords_from_text("GraphRAG 知识库 组件 Langflow GraphRAG")
    assert "GraphRAG" in kws or "知识库" in kws

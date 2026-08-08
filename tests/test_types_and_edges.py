"""KB 协议与边规范化单测。"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from lfx.schema.data import Data
from lfx_liam_bundle.graphrag.edges import (
    coerce_documents,
    normalize_edge_metadata,
    parse_edge_definition,
    stable_doc_id,
    weak_keywords_from_text,
)
from lfx_liam_bundle.graphrag.entity_extract import enrich_documents_for_graph
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
    assert "token" not in restored.public_summary() or restored.public_summary().get("token") is None


def test_from_data_rejects_plain_data() -> None:
    with pytest.raises(ValueError, match="知识库实例"):
        GraphRAGKnowledgeBase.from_data(Data(text="x", data={"foo": 1}))


def test_parse_edge_definition() -> None:
    assert parse_edge_definition("entities, entities") == ("entities", "entities")
    with pytest.raises(ValueError, match="两个部分"):
        parse_edge_definition("entities")


def test_normalize_and_coerce() -> None:
    meta = normalize_edge_metadata({"entities": "A, B; A", "keywords": ["x", "x"]}, ["entities", "keywords"])
    assert meta["entities"] == ["A", "B"]
    assert meta["keywords"] == ["x"]

    docs = coerce_documents(
        [
            Data(text="你好世界 GraphRAG", data={"entities": "Langflow"}),
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


def test_enrich_without_llm_fills_entities() -> None:
    docs = [Document(page_content="Langflow GraphRAG 示例文档", metadata={}, id="1")]
    out = enrich_documents_for_graph(
        docs,
        edge_fields=["entities", "keywords"],
        graph_mode="仅用已有metadata边",
        llm=None,
    )
    assert out[0].metadata.get("entities")
    assert out[0].metadata.get("keywords")

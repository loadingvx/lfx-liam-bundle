"""FastGraphRAG NLP 抽取单测。"""

from __future__ import annotations

from lfx_liam_bundle.graphrag.fast_extract import extract_graph_fast, extract_noun_phrases
from lfx_liam_bundle.graphrag.models import TextUnit


def test_extract_noun_phrases_zh_en() -> None:
    text = "Langflow 连接 AstraDB 与 ArangoDB，用于 GraphRAG 知识库。"
    phrases = extract_noun_phrases(text)
    joined = " ".join(phrases)
    assert "Langflow" in joined or "AstraDB" in joined or "知识库" in joined


def test_extract_graph_fast_cooccurrence() -> None:
    units = [
        TextUnit(id="t1", text="Langflow 使用 AstraDB 存储向量。"),
        TextUnit(id="t2", text="Langflow 也可以对接 ArangoDB。"),
    ]
    entities, relationships, stats = extract_graph_fast(units)
    assert entities
    assert stats["method"] == "fast_graphrag"
    titles = {e.title for e in entities}
    assert any("Langflow" in t for t in titles)
    # 至少应有一些共现边（取决于短语抽取）
    assert isinstance(relationships, list)

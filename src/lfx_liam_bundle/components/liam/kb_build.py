"""Build side: full GraphRAG indexing pipeline."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from lfx_liam_bundle.graphrag.extract_graph import DEFAULT_ENTITY_TYPES
from lfx_liam_bundle.graphrag.pipeline import run_indexing_pipeline
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBBuildComponent(Component):
    display_name = "GraphRAG Index Builder"
    description = (
        "Index documents into GraphRAG: Standard (LLM extract + gleaning) or "
        "FastGraphRAG (NLP noun phrases + co-occurrence, cheaper). "
        "Then Leiden communities → community reports → embeddings + ANN indexes."
    )
    name = "LiamGraphRAGBuild"
    icon = "DatabaseZap"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="KB instance",
            input_types=["Data"],
            info="Connect the output of GraphRAG Knowledge Base.",
            required=True,
        ),
        HandleInput(
            name="ingest_data",
            display_name="Documents to index",
            input_types=["Data", "DataFrame", "Table"],
            is_list=True,
            info="Raw or pre-split text. By default each item is token-chunked into TextUnits (can disable).",
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding model",
            input_types=["Embeddings"],
            required=True,
        ),
        HandleInput(
            name="llm",
            display_name="Language model (LLM)",
            input_types=["LanguageModel"],
            info="Standard: extract + reports. FastGraphRAG: LLM still needed for community reports.",
            required=True,
        ),
        DropdownInput(
            name="indexing_method",
            display_name="Indexing method",
            options=["Standard GraphRAG", "FastGraphRAG"],
            value="Standard GraphRAG",
            info=(
                "Standard: LLM entities/relationships + gleaning (higher quality, costlier). "
                "FastGraphRAG: NLP noun phrases + co-occurrence (faster/cheaper, noisier; good for Global summaries)."
            ),
        ),
        BoolInput(
            name="chunk_enabled",
            display_name="Enable built-in token chunking",
            value=True,
            info="Aligned with Microsoft Phase 1. If off, each input item becomes one TextUnit.",
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk size (tokens)",
            value=DEFAULT_CHUNK_SIZE,
            advanced=True,
            info="Default 1200 (same order as Microsoft defaults).",
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk overlap (tokens)",
            value=DEFAULT_CHUNK_OVERLAP,
            advanced=True,
        ),
        IntInput(
            name="max_gleanings",
            display_name="Gleaning rounds",
            value=1,
        ),
        BoolInput(
            name="extract_claims",
            display_name="Extract claims",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_cluster_size",
            display_name="Max community size",
            value=10,
            advanced=True,
        ),
        IntInput(
            name="max_community_levels",
            display_name="Max community levels",
            value=3,
            advanced=True,
        ),
        StrInput(
            name="entity_types",
            display_name="Entity types",
            value=", ".join(DEFAULT_ENTITY_TYPES),
            advanced=True,
            info="Comma-separated types for Standard extract.",
        ),
        DropdownInput(
            name="write_mode",
            display_name="Write mode",
            options=["Rebuild index", "Append merge"],
            value="Rebuild index",
        ),
    ]

    outputs = [
        Output(display_name="KB instance", name="kb_instance_out", method="build_and_index"),
        Output(display_name="Build summary", name="summary", method="build_summary"),
    ]

    _last_summary: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _run_build(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        types_raw = (self.entity_types or "").replace("，", ",").replace("、", ",")
        entity_types = [x.strip() for x in types_raw.split(",") if x.strip()]
        write_mode = self.write_mode or "Rebuild index"
        replace = write_mode in {"Rebuild index", "重建索引"}
        method_raw = self.indexing_method or "Standard GraphRAG"
        method = (
            "fast"
            if method_raw.startswith("Fast") or "FastGraphRAG" in method_raw
            else "standard"
        )
        try:
            kb, _index, summary = run_indexing_pipeline(
                kb,
                self.ingest_data,
                llm=self.llm,
                embedding=self.embedding_model,
                max_gleanings=int(self.max_gleanings if self.max_gleanings is not None else 1),
                max_cluster_size=int(self.max_cluster_size or 10),
                max_community_levels=int(self.max_community_levels or 3),
                entity_types=entity_types or None,
                replace=replace,
                extract_claims=bool(self.extract_claims) and method == "standard",
                chunk_enabled=bool(self.chunk_enabled),
                chunk_size=int(self.chunk_size or DEFAULT_CHUNK_SIZE),
                chunk_overlap=int(
                    self.chunk_overlap if self.chunk_overlap is not None else DEFAULT_CHUNK_OVERLAP
                ),
                indexing_method=method,
            )
        except Exception as e:
            msg = f"GraphRAG indexing failed: {e}"
            raise ValueError(msg) from e
        self._last_summary = summary
        self._last_kb = kb
        self.status = kb.message
        self.log(str(summary))
        return kb

    def build_and_index(self) -> Data:
        return self._run_build().to_data()

    def build_summary(self) -> Data:
        if self._last_summary is None:
            self._run_build()
        summary = self._last_summary or {}
        return Data(text=summary.get("message") or "Indexing complete", data=summary)

"""Retrieve side: Local / Global / DRIFT Search."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES, retrieve_documents
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBRetrieveComponent(Component):
    display_name = "GraphRAG Retrieve"
    description = (
        "GraphRAG retrieve: Local / Global / DRIFT Search. "
        "Supports token budgets, conversation history, and response style; "
        "DRIFT = community primer + Local follow-ups."
    )
    name = "LiamGraphRAGRetrieve"
    icon = "Search"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="KB instance",
            input_types=["Data"],
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding model",
            input_types=["Embeddings"],
            info="Required for Local / DRIFT.",
            required=False,
        ),
        HandleInput(
            name="llm",
            display_name="Language model (LLM)",
            input_types=["LanguageModel"],
            info="Required for Global / DRIFT; used by Local when generating answers.",
            required=False,
        ),
        MultilineInput(
            name="search_query",
            display_name="Query",
            tool_mode=True,
            required=True,
        ),
        DropdownInput(
            name="search_mode",
            display_name="Search mode",
            options=SEARCH_MODES,
            value="Local Search",
        ),
        MultilineInput(
            name="conversation_history",
            display_name="Conversation history",
            value="",
            advanced=True,
            info="Optional. Recent Q&A for Local/Global multi-turn context.",
        ),
        StrInput(
            name="response_type",
            display_name="Response style",
            value="Multi-paragraph answer",
            advanced=True,
            info="Examples: Multi-paragraph answer / bullet list / short conclusion.",
        ),
        IntInput(
            name="max_context_tokens",
            display_name="Context token budget",
            value=8000,
            advanced=True,
            info="Total budget for Local/Global context packing (tiktoken cl100k_base).",
        ),
        IntInput(
            name="text_unit_prop",
            display_name="Local text-unit share ×100",
            value=50,
            advanced=True,
            info="Share of budget for TextUnits (percent, default 50).",
        ),
        IntInput(
            name="community_prop",
            display_name="Local community-report share ×100",
            value=25,
            advanced=True,
            info="Share of budget for community reports (percent, default 25).",
        ),
        BoolInput(
            name="dynamic_community_selection",
            display_name="Global dynamic community selection",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="allow_general_knowledge",
            display_name="Global allow general knowledge",
            value=False,
            advanced=True,
            info="If on, Reduce may use world knowledge (higher hallucination risk).",
        ),
        IntInput(
            name="map_concurrency",
            display_name="Global map concurrency",
            value=1,
            advanced=True,
            info=">1 runs Map in parallel (watch LLM rate limits).",
        ),
        IntInput(
            name="community_level",
            display_name="Global community level",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="drift_n_depth",
            display_name="DRIFT follow-up rounds",
            value=2,
            advanced=True,
            info="Follow-up depth; higher is finer and costlier.",
        ),
        IntInput(
            name="drift_top_k_reports",
            display_name="DRIFT primer report count",
            value=5,
            advanced=True,
        ),
        IntInput(
            name="drift_max_follow_ups",
            display_name="DRIFT max follow-ups per round",
            value=3,
            advanced=True,
        ),
        IntInput(
            name="top_k_entities",
            display_name="Local entity count",
            value=8,
            advanced=True,
        ),
        IntInput(
            name="top_k_chunks",
            display_name="Local text-unit count",
            value=6,
            advanced=True,
        ),
        BoolInput(
            name="answer_with_llm",
            display_name="Local answer with LLM",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search"),
        Output(display_name="Answer / context", name="context", method="search_context"),
    ]

    _last_docs: list | None = None
    _last_text: str | None = None
    _last_meta: dict | None = None

    def _run(self):
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        mode = self.search_mode or "Local Search"
        if mode in {"Global Search", "DRIFT Search"} and self.llm is None:
            msg = f"{mode} requires an LLM connection."
            raise ValueError(msg)
        if mode in {"Local Search", "DRIFT Search"} and self.embedding_model is None:
            msg = f"{mode} requires an Embedding model."
            raise ValueError(msg)

        docs, text, meta = retrieve_documents(
            kb,
            self.search_query,
            embedding=self.embedding_model,
            llm=self.llm,
            search_mode=mode,
            community_level=int(self.community_level or 0),
            top_k_entities=int(self.top_k_entities or 8),
            top_k_chunks=int(self.top_k_chunks or 6),
            answer_with_llm=bool(self.answer_with_llm),
            dynamic_community_selection=bool(self.dynamic_community_selection),
            max_context_tokens=int(self.max_context_tokens or 8000),
            text_unit_prop=float(self.text_unit_prop or 50) / 100.0,
            community_prop=float(self.community_prop or 25) / 100.0,
            conversation_history=(self.conversation_history or "").strip() or None,
            response_type=(self.response_type or "Multi-paragraph answer").strip(),
            allow_general_knowledge=bool(self.allow_general_knowledge),
            map_concurrency=int(self.map_concurrency or 1),
            drift_n_depth=int(self.drift_n_depth or 2),
            drift_top_k_reports=int(self.drift_top_k_reports or 5),
            drift_max_follow_ups=int(self.drift_max_follow_ups or 3),
        )
        self._last_docs = docs
        self._last_text = text
        self._last_meta = meta
        self.status = f"{meta.get('mode')} done: {len(docs)} document/report item(s)."
        self.log(str(meta))
        return docs, text, meta

    def search(self) -> list[Data]:
        docs, _, _ = self._run()
        return docs_to_data(docs)

    def search_context(self) -> Data:
        if self._last_text is None:
            _, text, meta = self._run()
        else:
            text, meta = self._last_text, self._last_meta or {}
        return Data(text=text or "", data=meta or {})

"""Knowledge-base maintenance: stats / clear."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import clear_index, load_index
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase

_CONFIRM_PHRASE = "CONFIRM DELETE"


class GraphRAGKBMaintainComponent(Component):
    display_name = "GraphRAG Maintain"
    description = "Show GraphRAG knowledge-model stats, or clear the KB (destructive; confirmation required)."
    name = "LiamGraphRAGMaintain"
    icon = "Trash2"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="KB instance",
            input_types=["Data"],
            required=True,
        ),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["Stats", "Clear knowledge base"],
            value="Stats",
        ),
        StrInput(
            name="confirm_text",
            display_name="Clear confirmation phrase",
            value="",
            info=f"To clear, type exactly: {_CONFIRM_PHRASE}",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="KB instance", name="kb_instance_out", method="run_maintain"),
        Output(display_name="Operation result", name="result", method="run_result"),
    ]

    _last_result: dict | None = None

    def _execute(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        op = self.operation or "Stats"
        if op in {"Stats", "统计"}:
            index = load_index(kb)
            stats = index.stats()
            kb.document_count = stats["text_units"]
            kb.status = "ready" if kb.document_count or stats["entities"] else "empty"
            kb.message = (
                f"Stats: text units {stats['text_units']}, entities {stats['entities']}, "
                f"relationships {stats['relationships']}, communities {stats['communities']} "
                f"({stats['community_levels']} levels), reports {stats['community_reports']}, "
                f"claims {stats.get('covariates', 0)}."
            )
            result = {"operation": op, **stats, "message": kb.message}
        elif op in {"Clear knowledge base", "清空知识库"}:
            confirm = (self.confirm_text or "").strip()
            if confirm not in {_CONFIRM_PHRASE, "确认清空"}:
                msg = (
                    f"Clear is destructive. Type exactly in Clear confirmation phrase: {_CONFIRM_PHRASE}"
                )
                raise ValueError(msg)
            result = clear_index(kb)
            result["operation"] = op
        else:
            msg = f"Unknown operation: {op}"
            raise ValueError(msg)
        self._last_result = result
        self.status = result.get("message") or kb.message
        return kb

    def run_maintain(self) -> Data:
        return self._execute().to_data()

    def run_result(self) -> Data:
        if self._last_result is None:
            self._execute()
        result = self._last_result or {}
        return Data(text=result.get("message") or "Done", data=result)

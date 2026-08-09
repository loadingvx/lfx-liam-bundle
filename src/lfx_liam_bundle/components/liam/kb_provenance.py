"""Bidirectional provenance: entity ↔ text unit ↔ document."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.provenance import document_to_graph, entity_to_sources, text_unit_to_graph
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBProvenanceComponent(Component):
    display_name = "GraphRAG Provenance"
    description = (
        "Bidirectional provenance: entity → text units, text unit → entities, "
        "document → graph elements. Use to verify answers are grounded in source material."
    )
    name = "LiamGraphRAGProvenance"
    icon = "Link"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="KB instance",
            input_types=["Data"],
            required=True,
            info="Connect an indexed GraphRAG KB instance.",
        ),
        DropdownInput(
            name="lookup_mode",
            display_name="Lookup direction",
            options=[
                "Entity → Text Units",
                "Text Unit → Entities",
                "Document → Graph Elements",
            ],
            value="Entity → Text Units",
            info=(
                "Entity → Text Units: which TextUnits support an entity; "
                "Text Unit → Entities: entities/relationships from a unit; "
                "Document → Graph Elements: entities aggregated by document."
            ),
        ),
        StrInput(
            name="lookup_key",
            display_name="Lookup key",
            value="",
            info="Entity name/ID, TextUnit ID, or document ID/title depending on mode.",
            tool_mode=True,
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Provenance result", name="result", method="run_lookup"),
        Output(display_name="KB instance", name="kb_instance_out", method="pass_kb"),
    ]

    _last_result: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _execute(self) -> dict:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        self._last_kb = kb
        mode = self.lookup_mode or "Entity → Text Units"
        key = (self.lookup_key or "").strip()
        if not key:
            msg = "Enter a lookup key (entity name / text-unit ID / document ID)."
            raise ValueError(msg)

        try:
            index = load_index(kb)
        except Exception as e:  # noqa: BLE001
            msg = f"Failed to load knowledge base: {e}. Confirm indexing has completed."
            raise ValueError(msg) from e

        if mode in {"Entity → Text Units", "实体 → 原文"}:
            result = entity_to_sources(index, key)
        elif mode in {"Text Unit → Entities", "原文 → 实体"}:
            result = text_unit_to_graph(index, key)
        elif mode in {"Document → Graph Elements", "文档 → 图元素"}:
            result = document_to_graph(index, key)
        else:
            msg = f"Unknown lookup direction: {mode}"
            raise ValueError(msg)

        result["operation"] = mode
        self._last_result = result
        self.status = result.get("message") or "Provenance lookup complete"
        self.log(
            str({k: v for k, v in result.items() if k not in {"sources", "text_unit", "text_units"}})
        )
        return result

    def run_lookup(self) -> Data:
        result = self._execute()
        return Data(text=result.get("message") or "Done", data=result)

    def pass_kb(self) -> Data:
        if self._last_kb is None:
            self._execute()
        assert self._last_kb is not None
        return self._last_kb.to_data()

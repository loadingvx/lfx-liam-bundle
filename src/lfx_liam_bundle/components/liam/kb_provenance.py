"""双向溯源：实体↔原文↔文档（对齐微软 GraphRAG provenance）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import load_index
from lfx_liam_bundle.graphrag.provenance import document_to_graph, entity_to_sources, text_unit_to_graph
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBProvenanceComponent(Component):
    display_name = "GraphRAG 溯源查询"
    description = (
        "双向溯源：实体→原文、原文→实体、文档→图元素。"
        "用于核对答案是否锚定到源材料（微软 GraphRAG provenance）。"
    )
    name = "LiamGraphRAGProvenance"
    icon = "Link"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="知识库实例",
            input_types=["Data"],
            required=True,
            info="连接已建图的 GraphRAG 知识库实例。",
        ),
        DropdownInput(
            name="lookup_mode",
            display_name="查询方向",
            options=[
                "实体 → 原文",
                "原文 → 实体",
                "文档 → 图元素",
            ],
            value="实体 → 原文",
            info=(
                "实体→原文：看实体来自哪些 TextUnit；"
                "原文→实体：看某片段抽到了哪些实体/关系；"
                "文档→图元素：按文档聚合实体。"
            ),
        ),
        StrInput(
            name="lookup_key",
            display_name="查询键",
            value="",
            info="按模式填写：实体名/实体ID、文本单元ID、或文档ID/标题。",
            tool_mode=True,
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="溯源结果", name="result", method="run_lookup"),
        Output(display_name="知识库实例", name="kb_instance_out", method="pass_kb"),
    ]

    _last_result: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _execute(self) -> dict:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        self._last_kb = kb
        mode = self.lookup_mode or "实体 → 原文"
        key = (self.lookup_key or "").strip()
        if not key:
            msg = "请填写查询键（实体名/文本单元ID/文档ID）。"
            raise ValueError(msg)

        try:
            index = load_index(kb)
        except Exception as e:  # noqa: BLE001
            msg = f"加载知识库失败：{e}。请确认已完成入库建图。"
            raise ValueError(msg) from e

        if mode == "实体 → 原文":
            result = entity_to_sources(index, key)
        elif mode == "原文 → 实体":
            result = text_unit_to_graph(index, key)
        elif mode == "文档 → 图元素":
            result = document_to_graph(index, key)
        else:
            msg = f"未知查询方向：{mode}"
            raise ValueError(msg)

        result["operation"] = mode
        self._last_result = result
        self.status = result.get("message") or "溯源完成"
        self.log(
            str({k: v for k, v in result.items() if k not in {"sources", "text_unit", "text_units"}})
        )
        return result

    def run_lookup(self) -> Data:
        result = self._execute()
        return Data(text=result.get("message") or "完成", data=result)

    def pass_kb(self) -> Data:
        if self._last_kb is None:
            self._execute()
        assert self._last_kb is not None
        return self._last_kb.to_data()

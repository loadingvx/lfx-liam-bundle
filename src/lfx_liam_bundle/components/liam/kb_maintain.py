"""知识库维护：统计 / 清空（完整 GraphRAG 表）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import clear_index, load_index
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBMaintainComponent(Component):
    display_name = "GraphRAG 知识库维护"
    description = "统计 GraphRAG 知识模型规模，或清空（危险操作需确认）。"
    name = "LiamGraphRAGMaintain"
    icon = "Trash2"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="知识库实例",
            input_types=["Data"],
            required=True,
        ),
        DropdownInput(
            name="operation",
            display_name="操作",
            options=["统计", "清空知识库"],
            value="统计",
        ),
        StrInput(
            name="confirm_text",
            display_name="清空确认语",
            value="",
            info="清空时必须输入：确认清空",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance_out", method="run_maintain"),
        Output(display_name="操作结果", name="result", method="run_result"),
    ]

    _last_result: dict | None = None

    def _execute(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        op = self.operation or "统计"
        if op == "统计":
            index = load_index(kb)
            stats = index.stats()
            kb.document_count = stats["text_units"]
            kb.status = "ready" if kb.document_count or stats["entities"] else "empty"
            kb.message = (
                f"统计：文本单元 {stats['text_units']}，实体 {stats['entities']}，"
                f"关系 {stats['relationships']}，社区 {stats['communities']}（{stats['community_levels']} 层），"
                f"报告 {stats['community_reports']}，声明 {stats.get('covariates', 0)}。"
            )
            result = {"operation": op, **stats, "message": kb.message}
        elif op == "清空知识库":
            if (self.confirm_text or "").strip() != "确认清空":
                msg = "清空是危险操作。请在「清空确认语」中精确输入：确认清空"
                raise ValueError(msg)
            result = clear_index(kb)
            result["operation"] = op
        else:
            msg = f"未知操作：{op}"
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
        return Data(text=result.get("message") or "完成", data=result)

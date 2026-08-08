"""知识库维护：统计 / 按 ID 删除 / 清空。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, MessageTextInput, Output, StrInput
from lfx.schema.data import Data
from lfx_liam_bundle.graphrag import arango_adapter, astra_adapter
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBMaintainComponent(Component):
    display_name = "GraphRAG 知识库维护"
    description = "对知识库实例执行统计、按文档 ID 删除或清空（危险操作需确认）。"
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
            options=["统计", "按文档ID删除", "清空知识库"],
            value="统计",
        ),
        MessageTextInput(
            name="doc_ids",
            display_name="文档 ID 列表",
            info="按文档ID删除时使用，多个 ID 用逗号分隔。",
            tool_mode=True,
        ),
        StrInput(
            name="confirm_text",
            display_name="清空确认语",
            value="",
            info="清空知识库时必须输入：确认清空",
            advanced=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型（Astra 删除时可选）",
            input_types=["Embeddings"],
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance_out", method="run_maintain"),
        Output(display_name="操作结果", name="result", method="run_result"),
    ]

    _last_result: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _execute(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        op = self.operation or "统计"
        result: dict

        if op == "统计":
            if kb.backend == "astradb":
                count = astra_adapter.count_documents(kb)
            else:
                count = arango_adapter.count_documents(kb)
            kb.document_count = count
            kb.status = "ready" if count else "empty"
            kb.message = f"知识库「{kb.name}」当前文档数：{count}。"
            result = {"operation": op, "document_count": count, "message": kb.message}
        elif op == "按文档ID删除":
            raw = (self.doc_ids or "").strip()
            ids = [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
            if not ids:
                msg = "请填写要删除的文档 ID（doc_id），多个用逗号分隔。"
                raise ValueError(msg)
            if kb.backend == "astradb":
                result = astra_adapter.delete_by_ids(kb, ids, self.embedding_model)
            else:
                result = arango_adapter.delete_by_ids(kb, ids)
            result["operation"] = op
            try:
                kb.document_count = (
                    astra_adapter.count_documents(kb)
                    if kb.backend == "astradb"
                    else arango_adapter.count_documents(kb)
                )
            except Exception:  # noqa: BLE001
                pass
            kb.status = "ready" if kb.document_count else "empty"
        elif op == "清空知识库":
            if (self.confirm_text or "").strip() != "确认清空":
                msg = "清空是危险操作。请在「清空确认语」中精确输入：确认清空"
                raise ValueError(msg)
            if kb.backend == "astradb":
                result = astra_adapter.clear_collection(kb)
            else:
                result = arango_adapter.clear_collection(kb)
            result["operation"] = op
            kb.document_count = 0
            kb.status = "empty"
        else:
            msg = f"未知操作：{op}"
            raise ValueError(msg)

        self._last_result = result
        self._last_kb = kb
        self.status = result.get("message") or kb.message
        return kb

    def run_maintain(self) -> Data:
        return self._execute().to_data()

    def run_result(self) -> Data:
        if self._last_result is None:
            self._execute()
        result = self._last_result or {}
        return Data(text=result.get("message") or "完成", data=result)

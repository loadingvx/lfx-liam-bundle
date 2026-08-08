"""检索侧：GraphRAG 检索（Astra 移植官方 GraphRetriever，Arango 自研）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import docs_to_data
from lfx.io import DropdownInput, HandleInput, IntInput, MultilineInput, NestedDictInput, Output, StrInput
from lfx.schema.data import Data
from lfx_liam_bundle.graphrag.retrieve import retrieve_documents, traversal_strategy_names
from lfx_liam_bundle.graphrag.types import DEFAULT_EDGE_DEFINITION, GraphRAGKnowledgeBase


class GraphRAGKBRetrieveComponent(Component):
    display_name = "GraphRAG 检索"
    description = "对 GraphRAG 知识库实例执行向量召回 + 图遍历检索（用法类似官方 Graph RAG）。"
    name = "LiamGraphRAGRetrieve"
    icon = "Search"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="知识库实例",
            input_types=["Data"],
            info="连接「GraphRAG 知识库」或「入库建图」输出的同一实例。",
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型",
            input_types=["Embeddings"],
            info="应与入库时使用的模型一致。",
            required=True,
        ),
        MultilineInput(
            name="search_query",
            display_name="检索问题",
            tool_mode=True,
            required=True,
        ),
        StrInput(
            name="edge_definition",
            display_name="边定义",
            value=DEFAULT_EDGE_DEFINITION,
            info="例如 entities,entities 或 mentions,Id()。留空则用知识库默认。",
        ),
        DropdownInput(
            name="strategy",
            display_name="遍历策略",
            options=traversal_strategy_names(),
            value=(traversal_strategy_names() or ["Eager"])[0],
            info="Astra 路径使用 GraphRetriever 策略；Arango 路径主要使用深度参数。",
        ),
        IntInput(
            name="top_k",
            display_name="返回条数",
            value=4,
            advanced=True,
        ),
        IntInput(
            name="depth",
            display_name="遍历深度",
            value=1,
            advanced=True,
            info="Arango 图遍历深度；Astra 也可通过策略参数覆盖。",
        ),
        NestedDictInput(
            name="strategy_kwargs",
            display_name="策略参数",
            info="传给 GraphRetriever Strategy 的额外参数（如 start_k/select_k/max_depth）。",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="检索结果", name="results", method="search"),
        Output(display_name="上下文文本", name="context", method="search_context"),
    ]

    _last_docs: list | None = None

    def _search_docs(self):
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        if kb.status == "empty" and kb.document_count == 0:
            # 仍允许检索，但给出明确提示
            self.log("知识库可能为空：若结果为空，请先运行「入库建图」。")

        edge_definition = (self.edge_definition or "").strip() or kb.edge_definition
        kwargs = self.strategy_kwargs or {}
        docs = retrieve_documents(
            kb,
            self.search_query,
            embedding=self.embedding_model,
            edge_definition=edge_definition,
            strategy=self.strategy or "Eager",
            strategy_kwargs=kwargs if isinstance(kwargs, dict) else {},
            top_k=int(self.top_k or 4),
            depth=int(self.depth or 1),
        )
        self._last_docs = docs
        if not docs:
            self.status = "未检索到结果。请确认已入库建图，且边字段（如 entities）非空。"
        else:
            self.status = f"检索到 {len(docs)} 条结果。"
        return docs

    def search(self) -> list[Data]:
        return docs_to_data(self._search_docs())

    def search_context(self) -> Data:
        docs = self._last_docs if self._last_docs is not None else self._search_docs()
        if not docs:
            text = "（无检索结果。请先完成入库建图，或更换检索问题/边定义。）"
            return Data(text=text, data={"results": [], "message": text})
        parts = []
        for i, doc in enumerate(docs, start=1):
            parts.append(f"[{i}] {doc.page_content}")
        text = "\n\n".join(parts)
        return Data(text=text, data={"count": len(docs)})

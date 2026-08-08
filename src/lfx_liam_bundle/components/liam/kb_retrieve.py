"""检索侧：Local Search / Global Search。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES, retrieve_documents
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBRetrieveComponent(Component):
    display_name = "GraphRAG 检索"
    description = (
        "真正的 GraphRAG 检索：Local Search（实体邻域+原文）或 "
        "Global Search（社区报告 Map-Reduce，可动态社区选择）。"
    )
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
            info="Local Search 必需；应与建库时使用的模型一致。",
            required=False,
        ),
        HandleInput(
            name="llm",
            display_name="语言模型 LLM",
            input_types=["LanguageModel"],
            info="Global Search 必需；Local Search 用于生成最终答案（推荐连接）。",
            required=False,
        ),
        MultilineInput(
            name="search_query",
            display_name="检索问题",
            tool_mode=True,
            required=True,
            info="Local：适合具体实体问题；Global：适合主题/全局总结类问题。",
        ),
        DropdownInput(
            name="search_mode",
            display_name="检索模式",
            options=SEARCH_MODES,
            value="Local Search",
            info="Local：实体邻域+关系+社区摘要+原文；Global：社区报告 Map-Reduce。",
        ),
        BoolInput(
            name="dynamic_community_selection",
            display_name="Global 动态社区选择",
            value=False,
            advanced=True,
            info="开启后从粗到细剪枝无关社区（对齐微软动态社区选择），降低无效 Map 成本。",
        ),
        IntInput(
            name="community_level",
            display_name="Global 社区层级",
            value=0,
            advanced=True,
            info="0 为最粗层级。仅在关闭动态社区选择时生效。",
        ),
        IntInput(
            name="top_k_entities",
            display_name="Local 实体数",
            value=8,
            advanced=True,
        ),
        IntInput(
            name="top_k_chunks",
            display_name="Local 原文片段数",
            value=6,
            advanced=True,
        ),
        BoolInput(
            name="answer_with_llm",
            display_name="Local 用 LLM 生成答案",
            value=True,
            advanced=True,
            info="关闭则输出检索上下文原文（便于自行接到 Prompt 组件）。",
        ),
    ]

    outputs = [
        Output(display_name="检索结果", name="results", method="search"),
        Output(display_name="答案/上下文", name="context", method="search_context"),
    ]

    _last_docs: list | None = None
    _last_text: str | None = None
    _last_meta: dict | None = None

    def _run(self):
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        mode = self.search_mode or "Local Search"
        if mode == "Global Search" and self.llm is None:
            msg = "Global Search 必须连接 LLM（Map-Reduce 需要语言模型）。"
            raise ValueError(msg)
        if mode == "Local Search" and self.embedding_model is None:
            msg = "Local Search 必须连接 Embedding 模型（实体描述向量检索）。"
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
        )
        self._last_docs = docs
        self._last_text = text
        self._last_meta = meta
        self.status = f"{meta.get('mode')} 完成：文档/报告 {len(docs)} 条。"
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

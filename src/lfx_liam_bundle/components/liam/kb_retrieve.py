"""检索侧：Local Search / Global Search。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import docs_to_data
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.retrieve import SEARCH_MODES, retrieve_documents
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBRetrieveComponent(Component):
    display_name = "GraphRAG 检索"
    description = (
        "GraphRAG 检索：Local / Global / DRIFT Search。"
        "支持 token 预算、对话历史、回答形式；DRIFT=社区 Primer+Local 追问。"
    )
    name = "LiamGraphRAGRetrieve"
    icon = "Search"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="知识库实例",
            input_types=["Data"],
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型",
            input_types=["Embeddings"],
            info="Local / DRIFT 必需。",
            required=False,
        ),
        HandleInput(
            name="llm",
            display_name="语言模型 LLM",
            input_types=["LanguageModel"],
            info="Global / DRIFT 必需；Local 用于生成答案。",
            required=False,
        ),
        MultilineInput(
            name="search_query",
            display_name="检索问题",
            tool_mode=True,
            required=True,
        ),
        DropdownInput(
            name="search_mode",
            display_name="检索模式",
            options=SEARCH_MODES,
            value="Local Search",
        ),
        MultilineInput(
            name="conversation_history",
            display_name="对话历史",
            value="",
            advanced=True,
            info="可选。多轮对话时填入近期问答，供 Local/Global 使用。",
        ),
        StrInput(
            name="response_type",
            display_name="回答形式",
            value="多段落中文回答",
            advanced=True,
            info="例如：多段落中文回答 / 要点列表 / 简短结论。",
        ),
        IntInput(
            name="max_context_tokens",
            display_name="上下文 token 预算",
            value=8000,
            advanced=True,
            info="Local/Global 装配上下文的总预算（tiktoken cl100k_base）。",
        ),
        IntInput(
            name="text_unit_prop",
            display_name="Local 原文占比×100",
            value=50,
            advanced=True,
            info="原文 TextUnit 占预算比例（百分比，默认 50）。",
        ),
        IntInput(
            name="community_prop",
            display_name="Local 社区报告占比×100",
            value=25,
            advanced=True,
            info="社区报告占预算比例（百分比，默认 25）。",
        ),
        BoolInput(
            name="dynamic_community_selection",
            display_name="Global 动态社区选择",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="allow_general_knowledge",
            display_name="Global 允许通用知识",
            value=False,
            advanced=True,
            info="开启后 Reduce 可结合世界知识（可能增加幻觉）。",
        ),
        IntInput(
            name="map_concurrency",
            display_name="Global Map 并发",
            value=1,
            advanced=True,
            info=">1 时并行 Map（注意 LLM 限流）。",
        ),
        IntInput(
            name="community_level",
            display_name="Global 社区层级",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="drift_n_depth",
            display_name="DRIFT 追问轮数",
            value=2,
            advanced=True,
            info="Follow-Up 迭代深度，越大越细也越贵。",
        ),
        IntInput(
            name="drift_top_k_reports",
            display_name="DRIFT Primer 报告数",
            value=5,
            advanced=True,
        ),
        IntInput(
            name="drift_max_follow_ups",
            display_name="DRIFT 每轮最多追问",
            value=3,
            advanced=True,
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
        if mode in {"Global Search", "DRIFT Search"} and self.llm is None:
            msg = f"{mode} 必须连接 LLM。"
            raise ValueError(msg)
        if mode in {"Local Search", "DRIFT Search"} and self.embedding_model is None:
            msg = f"{mode} 必须连接 Embedding 模型。"
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
            response_type=(self.response_type or "多段落中文回答").strip(),
            allow_general_knowledge=bool(self.allow_general_knowledge),
            map_concurrency=int(self.map_concurrency or 1),
            drift_n_depth=int(self.drift_n_depth or 2),
            drift_top_k_reports=int(self.drift_top_k_reports or 5),
            drift_max_follow_ups=int(self.drift_max_follow_ups or 3),
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

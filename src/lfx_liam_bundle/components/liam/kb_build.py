"""建库侧：完整 GraphRAG 索引流水线。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from lfx_liam_bundle.graphrag.extract_graph import DEFAULT_ENTITY_TYPES
from lfx_liam_bundle.graphrag.pipeline import run_indexing_pipeline
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBBuildComponent(Component):
    display_name = "GraphRAG 入库建图"
    description = (
        "GraphRAG 建库：标准（LLM 抽取+Gleaning）或 FastGraphRAG（NLP 名词短语+共现，更便宜）。"
        "随后 Leiden 社区→社区报告→向量落库+ANN 索引。"
    )
    name = "LiamGraphRAGBuild"
    icon = "DatabaseZap"

    inputs = [
        HandleInput(
            name="kb_instance",
            display_name="知识库实例",
            input_types=["Data"],
            info="连接「GraphRAG 知识库」组件的输出。",
            required=True,
        ),
        HandleInput(
            name="ingest_data",
            display_name="待入库文档",
            input_types=["Data", "DataFrame", "Table"],
            is_list=True,
            info="原始文档或已切分文本。默认会按 token 再切成 TextUnit（可关闭）。",
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型",
            input_types=["Embeddings"],
            required=True,
        ),
        HandleInput(
            name="llm",
            display_name="语言模型 LLM",
            input_types=["LanguageModel"],
            info="标准模式：抽取+报告。FastGraphRAG：仅社区报告需要 LLM。",
            required=True,
        ),
        DropdownInput(
            name="indexing_method",
            display_name="建图模式",
            options=["标准 GraphRAG", "FastGraphRAG"],
            value="标准 GraphRAG",
            info=(
                "标准：LLM 实体/关系+Gleaning（质量高、更贵）。"
                "FastGraphRAG：NLP 名词短语+共现关系（更快更便宜，图更噪，适合偏 Global 摘要）。"
            ),
        ),
        BoolInput(
            name="chunk_enabled",
            display_name="启用内置 token 切块",
            value=True,
            info="对齐微软 Phase 1。关闭则把每条输入当作一个 TextUnit。",
        ),
        IntInput(
            name="chunk_size",
            display_name="切块大小（tokens）",
            value=DEFAULT_CHUNK_SIZE,
            advanced=True,
            info="默认 1200（微软默认同量级）。",
        ),
        IntInput(
            name="chunk_overlap",
            display_name="切块重叠（tokens）",
            value=DEFAULT_CHUNK_OVERLAP,
            advanced=True,
        ),
        IntInput(
            name="max_gleanings",
            display_name="Gleaning 轮数",
            value=1,
        ),
        BoolInput(
            name="extract_claims",
            display_name="抽取事实声明 Claims",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="max_cluster_size",
            display_name="社区最大规模",
            value=10,
            advanced=True,
        ),
        IntInput(
            name="max_community_levels",
            display_name="社区最大层数",
            value=3,
            advanced=True,
        ),
        StrInput(
            name="entity_types",
            display_name="实体类型",
            value="、".join(DEFAULT_ENTITY_TYPES),
            advanced=True,
        ),
        DropdownInput(
            name="write_mode",
            display_name="写入模式",
            options=["重建索引", "追加合并"],
            value="重建索引",
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance_out", method="build_and_index"),
        Output(display_name="建库汇总", name="summary", method="build_summary"),
    ]

    _last_summary: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _run_build(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        types_raw = (self.entity_types or "").replace("，", "、").replace(",", "、")
        entity_types = [x.strip() for x in types_raw.split("、") if x.strip()]
        replace = (self.write_mode or "重建索引") == "重建索引"
        method = (
            "fast"
            if (self.indexing_method or "").startswith("Fast")
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
                chunk_overlap=int(self.chunk_overlap if self.chunk_overlap is not None else DEFAULT_CHUNK_OVERLAP),
                indexing_method=method,
            )
        except Exception as e:
            msg = f"GraphRAG 建库失败：{e}"
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
        return Data(text=summary.get("message") or "建库完成", data=summary)

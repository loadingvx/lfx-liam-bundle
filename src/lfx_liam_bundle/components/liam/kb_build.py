"""建库侧：完整 GraphRAG 索引流水线（抽取+Gleaning+分层社区+报告+向量化）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, Output, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.extract_graph import DEFAULT_ENTITY_TYPES
from lfx_liam_bundle.graphrag.pipeline import run_indexing_pipeline
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBBuildComponent(Component):
    display_name = "GraphRAG 入库建图"
    description = (
        "完整 GraphRAG 建库：TextUnit→实体/关系抽取（含 Data Gleaning）→"
        "分层社区检测→社区报告→向量索引落库。"
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
            info="文档或文本块（TextUnit）列表。建议先切分再入库。",
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型",
            input_types=["Embeddings"],
            info="用于 TextUnit / 实体描述 / 社区报告向量化（Local Search 依赖）。",
            required=True,
        ),
        HandleInput(
            name="llm",
            display_name="语言模型 LLM",
            input_types=["LanguageModel"],
            info="必须连接：实体关系抽取、Data Gleaning、社区报告均依赖 LLM。",
            required=True,
        ),
        IntInput(
            name="max_gleanings",
            display_name="Gleaning 轮数",
            value=1,
            info="Data Gleaning 补抽轮数（对齐微软 GraphRAG）。建议 1~2；0 表示关闭补抽。",
        ),
        BoolInput(
            name="extract_claims",
            display_name="抽取事实声明 Claims",
            value=False,
            advanced=True,
            info="可选（微软默认关闭）。开启后额外抽取 Covariates，供 Local Search 使用，费用更高。",
        ),
        IntInput(
            name="max_cluster_size",
            display_name="社区最大规模",
            value=10,
            advanced=True,
            info="分层社区递归分裂阈值（实体数）。",
        ),
        IntInput(
            name="max_community_levels",
            display_name="社区最大层数",
            value=3,
            advanced=True,
            info="社区层次深度。层数越多，Global Search 粒度越细。",
        ),
        StrInput(
            name="entity_types",
            display_name="实体类型",
            value="、".join(DEFAULT_ENTITY_TYPES),
            advanced=True,
            info="逗号/顿号分隔的实体类型约束。",
        ),
        DropdownInput(
            name="write_mode",
            display_name="写入模式",
            options=["重建索引", "追加合并"],
            value="重建索引",
            info="重建：清空后全量写入。追加：与已有实体/关系合并后重建社区与报告。",
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
                extract_claims=bool(self.extract_claims),
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
        text = summary.get("message") or "建库完成"
        return Data(text=text, data=summary)

"""建库侧：文档入库 + 向量索引 + 图边创建。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, HandleInput, Output, StrInput
from lfx.schema.data import Data
from lfx_liam_bundle.graphrag import arango_adapter, astra_adapter
from lfx_liam_bundle.graphrag.edges import coerce_documents
from lfx_liam_bundle.graphrag.entity_extract import enrich_documents_for_graph
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBBuildComponent(Component):
    display_name = "GraphRAG 入库建图"
    description = "向知识库实例写入文档、构建向量索引并生成图边（一次完成建库侧全流程）。"
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
            info="文档或文本块列表。",
            required=True,
        ),
        HandleInput(
            name="embedding_model",
            display_name="Embedding 模型",
            input_types=["Embeddings"],
            info="用于生成向量索引。",
            required=True,
        ),
        DropdownInput(
            name="write_mode",
            display_name="写入模式",
            options=["按文档ID覆盖", "追加"],
            value="按文档ID覆盖",
            info="覆盖模式会先按 doc_id 删除再写入，适合重复导入。",
        ),
        DropdownInput(
            name="graph_mode",
            display_name="建图模式",
            options=["仅用已有metadata边", "LLM抽取实体写入边"],
            value="仅用已有metadata边",
            info="若选择 LLM 抽取，请连接下方语言模型。",
        ),
        HandleInput(
            name="llm",
            display_name="实体抽取 LLM（可选）",
            input_types=["LanguageModel"],
            required=False,
            info="建图模式为 LLM 抽取时使用。",
        ),
        StrInput(
            name="edge_definition",
            display_name="边定义（可选覆盖）",
            value="",
            advanced=True,
            info="留空则使用知识库实例上的默认边定义。",
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance_out", method="build_and_index"),
        Output(display_name="入库汇总", name="summary", method="build_summary"),
    ]

    _last_summary: dict | None = None
    _last_kb: GraphRAGKnowledgeBase | None = None

    def _run_build(self) -> GraphRAGKnowledgeBase:
        kb = GraphRAGKnowledgeBase.from_data(self.kb_instance)
        documents = coerce_documents(self.ingest_data)
        if not documents:
            msg = "没有可入库的有效文档（文本为空）。请检查「待入库文档」输入。"
            raise ValueError(msg)

        if self.edge_definition and str(self.edge_definition).strip():
            kb.edge_definition = str(self.edge_definition).strip()

        graph_mode = self.graph_mode or "仅用已有metadata边"
        if graph_mode == "LLM抽取实体写入边" and self.llm is None:
            msg = "已选择「LLM抽取实体写入边」，但未连接语言模型。请连接 LLM，或改回「仅用已有metadata边」。"
            raise ValueError(msg)

        documents = enrich_documents_for_graph(
            documents,
            edge_fields=kb.edge_fields,
            graph_mode=graph_mode,
            llm=self.llm,
        )

        if kb.backend == "astradb":
            kb, summary = astra_adapter.ingest_documents(
                kb, documents, self.embedding_model, mode=self.write_mode or "按文档ID覆盖"
            )
        elif kb.backend == "arangodb":
            kb, summary = arango_adapter.ingest_documents(
                kb, documents, self.embedding_model, mode=self.write_mode or "按文档ID覆盖"
            )
        else:
            msg = f"不支持的后端：{kb.backend}"
            raise ValueError(msg)

        summary["graph_mode"] = graph_mode
        summary["edge_definition"] = kb.edge_definition
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
        text = summary.get("message") or "入库完成"
        return Data(text=text, data=summary)

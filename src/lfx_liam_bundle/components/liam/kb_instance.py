"""建库侧：GraphRAG 知识库实例（创建/连接）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_liam_bundle.graphrag.kg_store import ensure_kg_schema, load_index
from lfx_liam_bundle.graphrag.types import GraphRAGKnowledgeBase


class GraphRAGKBInstanceComponent(Component):
    display_name = "GraphRAG 知识库"
    description = "创建或连接 GraphRAG 知识库实例（AstraDB / ArangoDB）。建库与检索都围绕此实例。"
    name = "LiamGraphRAGKB"
    icon = "Database"

    inputs = [
        DropdownInput(
            name="backend",
            display_name="存储后端",
            options=["AstraDB", "ArangoDB"],
            value="AstraDB",
            info="仅支持 AstraDB 与 ArangoDB。",
            required=True,
        ),
        StrInput(
            name="kb_name",
            display_name="知识库名称",
            value="default",
            info="用于界面识别的显示名。",
            required=True,
        ),
        StrInput(
            name="collection_name",
            display_name="知识库前缀名",
            value="liam_graphrag",
            info=(
                "存储前缀，系统会自动创建 "
                "`{前缀}_chunks/_entities/_relationships/_communities/_reports` 等集合。"
                "不要手动加 `_chunks` 后缀。"
            ),
            required=True,
        ),
        BoolInput(
            name="create_if_missing",
            display_name="不存在则创建",
            value=True,
            info="目标集合不存在时自动创建。",
        ),
        MessageTextInput(
            name="api_endpoint",
            display_name="Astra / Data API Endpoint",
            info="云上 Astra Endpoint，或本地 HCD Data API（如 http://localhost:8181）。",
        ),
        SecretStrInput(
            name="token",
            display_name="Astra Token",
            info="仅云上 Astra 需要。本地 HCD 用下方用户名密码。",
        ),
        DropdownInput(
            name="data_api_environment",
            display_name="Data API 环境",
            options=["astra", "hcd"],
            value="astra",
            advanced=True,
            info="astra=云上 AstraDB；hcd=本地/自建 Data API（用户名密码）。",
        ),
        StrInput(
            name="data_api_username",
            display_name="Data API 用户名",
            value="",
            advanced=True,
            info="仅 hcd 环境需要（如 cassandra）。",
        ),
        SecretStrInput(
            name="data_api_password",
            display_name="Data API 密码",
            advanced=True,
            info="仅 hcd 环境需要。",
        ),
        StrInput(
            name="keyspace",
            display_name="Astra / Data API Keyspace",
            value="default_keyspace",
            advanced=True,
        ),
        MessageTextInput(
            name="arango_url",
            display_name="ArangoDB 地址",
            value="http://localhost:8529",
            info="仅 ArangoDB 需要。",
        ),
        StrInput(
            name="arango_username",
            display_name="ArangoDB 用户名",
            value="root",
        ),
        SecretStrInput(
            name="arango_password",
            display_name="ArangoDB 密码",
        ),
        StrInput(
            name="arango_database",
            display_name="ArangoDB 数据库",
            value="_system",
        ),
        StrInput(
            name="graph_name",
            display_name="Arango 图名称",
            value="",
            advanced=True,
            info="留空则自动使用「前缀名_kg_graph」。",
        ),
        BoolInput(
            name="use_vector_index",
            display_name="启用向量库 ANN 检索",
            value=True,
            info=(
                "默认开启。Astra 使用 `$vector` 近似检索；"
                "Arango 创建 Faiss 向量索引（可用 IVF+HNSW factory）并用 AQL 近似检索。"
                "失败时默认回退精确余弦，避免检索直接中断。"
            ),
        ),
        BoolInput(
            name="ann_fallback_exact",
            display_name="ANN 失败回退精确余弦",
            value=True,
            advanced=True,
            info="关闭后：向量索引/检索失败会直接报错，便于排查环境。",
        ),
        StrInput(
            name="vector_index_factory",
            display_name="Arango 向量索引 Factory",
            value="IVF100_HNSW10,Flat",
            advanced=True,
            info=(
                "仅 Arango。Faiss factory，默认 IVF+HNSW。"
                "系统会按文档数自动改写 IVF 基数，避免小库建索引失败。"
            ),
        ),
        StrInput(
            name="metric",
            display_name="向量相似度",
            value="cosine",
            advanced=True,
            info="cosine（推荐）/ l2 / innerProduct（Arango）或等价 Astra 度量。",
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance", method="build_kb"),
    ]

    def build_kb(self) -> Data:
        backend = "astradb" if self.backend == "AstraDB" else "arangodb"
        kb = GraphRAGKnowledgeBase(
            backend=backend,  # type: ignore[arg-type]
            name=(self.kb_name or "default").strip(),
            collection_name=(self.collection_name or "").strip(),
            api_endpoint=(self.api_endpoint or "").strip(),
            token=self.token or "",
            keyspace=(self.keyspace or "default_keyspace").strip(),
            data_api_environment=(  # type: ignore[arg-type]
                "hcd" if (self.data_api_environment or "astra") == "hcd" else "astra"
            ),
            data_api_username=(self.data_api_username or "").strip(),
            data_api_password=self.data_api_password or "",
            arango_url=(self.arango_url or "").strip(),
            arango_username=(self.arango_username or "root").strip(),
            arango_password=self.arango_password or "",
            arango_database=(self.arango_database or "_system").strip(),
            graph_name=(self.graph_name or "").strip(),
            use_vector_index=bool(self.use_vector_index),
            ann_fallback_exact=bool(self.ann_fallback_exact),
            vector_index_factory=(self.vector_index_factory or "IVF100_HNSW10,Flat").strip(),
            metric=(self.metric or "cosine").strip() or "cosine",
        )
        try:
            ensure_kg_schema(kb, create_if_missing=bool(self.create_if_missing))
            try:
                index = load_index(kb)
                kb.document_count = len(index.text_units)
                if index.entities or index.text_units:
                    kb.status = "ready"
                    ann = (
                        "向量ANN=开（Astra `$vector` / Arango Faiss）"
                        if kb.use_vector_index
                        else "向量ANN=关（精确余弦）"
                    )
                    kb.message = (
                        f"已连接 GraphRAG 知识库「{kb.name}」[{kb.backend}]："
                        f"文本单元 {len(index.text_units)}，实体 {len(index.entities)}，"
                        f"关系 {len(index.relationships)}，社区 {len(index.communities)}，"
                        f"报告 {len(index.community_reports)}；{ann}。"
                    )
                else:
                    kb.status = "empty"
                    kb.message = (
                        f"已连接 GraphRAG 知识库「{kb.name}」，尚未建图，请运行「入库建图」。"
                    )
            except Exception:
                kb.status = "empty"
                kb.message = f"已初始化 GraphRAG 存储骨架「{kb.collection_name}」，可开始入库建图。"
        except Exception as e:
            kb.status = "error"
            kb.message = f"连接 GraphRAG 知识库失败：{e}"
            self.status = kb.message
            raise ValueError(kb.message) from e

        self.status = kb.message
        self.log(str(kb.public_summary()))
        return kb.to_data()

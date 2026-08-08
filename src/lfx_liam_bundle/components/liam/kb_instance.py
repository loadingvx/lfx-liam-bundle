"""建库侧：GraphRAG 知识库实例（创建/连接）。"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx_liam_bundle.graphrag import arango_adapter, astra_adapter
from lfx_liam_bundle.graphrag.types import DEFAULT_EDGE_DEFINITION, DEFAULT_EDGE_FIELDS, GraphRAGKnowledgeBase


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
            display_name="集合/表名",
            value="liam_graphrag_chunks",
            info="Astra Collection 或 Arango 文档集合名。",
            required=True,
        ),
        BoolInput(
            name="create_if_missing",
            display_name="不存在则创建",
            value=True,
            info="目标集合不存在时自动创建。",
        ),
        StrInput(
            name="edge_definition",
            display_name="默认边定义",
            value=DEFAULT_EDGE_DEFINITION,
            info="与检索组件默认一致，例如 entities,entities",
            advanced=True,
        ),
        # Astra
        MessageTextInput(
            name="api_endpoint",
            display_name="Astra API Endpoint",
            info="仅 AstraDB 需要。",
        ),
        SecretStrInput(
            name="token",
            display_name="Astra Token",
            info="仅 AstraDB 需要。",
        ),
        StrInput(
            name="keyspace",
            display_name="Astra Keyspace",
            value="default_keyspace",
            advanced=True,
        ),
        # Arango
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
            info="留空则自动使用「集合名_graph」。",
        ),
    ]

    outputs = [
        Output(display_name="知识库实例", name="kb_instance", method="build_kb"),
    ]

    def build_kb(self) -> Data:
        backend = "astradb" if self.backend == "AstraDB" else "arangodb"
        edge_definition = (self.edge_definition or DEFAULT_EDGE_DEFINITION).strip()
        kb = GraphRAGKnowledgeBase(
            backend=backend,  # type: ignore[arg-type]
            name=(self.kb_name or "default").strip(),
            collection_name=(self.collection_name or "").strip(),
            edge_fields=list(DEFAULT_EDGE_FIELDS),
            edge_definition=edge_definition,
            api_endpoint=(self.api_endpoint or "").strip(),
            token=self.token or "",
            keyspace=(self.keyspace or "default_keyspace").strip(),
            arango_url=(self.arango_url or "").strip(),
            arango_username=(self.arango_username or "root").strip(),
            arango_password=self.arango_password or "",
            arango_database=(self.arango_database or "_system").strip(),
            graph_name=(self.graph_name or "").strip(),
        )
        try:
            if kb.backend == "astradb":
                kb = astra_adapter.connect_and_probe(kb, create_if_missing=bool(self.create_if_missing))
            else:
                kb = arango_adapter.connect_and_probe(kb, create_if_missing=bool(self.create_if_missing))
        except Exception as e:  # noqa: BLE001
            kb.status = "error"
            kb.message = str(e)
            self.status = kb.message
            raise ValueError(kb.message) from e

        self.status = kb.message
        self.log(str(kb.public_summary()))
        return kb.to_data()

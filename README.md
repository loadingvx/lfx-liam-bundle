# Liam GraphRAG Bundle

以 **知识库实例** 为边界的 GraphRAG 全流程组件：建库侧完成入库 / 向量索引 / 图边创建，检索侧对同一实例做 GraphRAG 查询。

后端支持：**AstraDB**、**ArangoDB**。

## 组件

| 侧 | 组件 | 作用 |
|----|------|------|
| 建库 | **GraphRAG 知识库** | 创建/连接知识库实例 |
| 建库 | **GraphRAG 入库建图** | 文档入库 + 索引 + 建图 |
| 检索 | **GraphRAG 检索** | 向量召回 + 图遍历（Astra 使用 GraphRetriever） |
| 维护 | **GraphRAG 知识库维护** | 统计 / 按 ID 删除 / 清空 |

## 推荐 Flow

```text
GraphRAG 知识库 ──KB实例──► GraphRAG 入库建图 ──同一KB实例──► GraphRAG 检索 ──► Prompt/LLM
                              ▲
                     文档切分 + Embedding
```

1. 配置「GraphRAG 知识库」（选 AstraDB 或 ArangoDB，填连接与集合名）
2. 将文档/切分结果与 Embedding 接入「入库建图」
3. 将同一知识库实例接到「GraphRAG 检索」，输入问题即可

边定义默认 `entities,entities`（可与官方 Graph RAG 语义对齐）。无 LLM 时会用文本弱关键词自动填充 `entities`/`keywords`，保证图边可用。

## 环境

```bash
./scripts/setup-env.sh
mise exec -- uv run lfx extension validate .
mise exec -- uv run pytest
./scripts/deploy-to-docker.sh
```

UI：http://localhost:5173 → Components → 搜索 `GraphRAG`。

## 依赖说明

- Astra：`langchain-astradb`、`astrapy`、`langchain-graph-retriever`、`graph-retriever`
- Arango：`python-arango`（向量相似度在适配器内计算并做图扩展）

安装到 Langflow 运行环境后，**无需**修改 `SIDEBAR_BUNDLES`。

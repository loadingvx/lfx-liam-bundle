# 架构说明

## 定位

`lfx-liam-bundle` 实现对齐微软 GraphRAG 默认 dataflow 的知识库扩展（非 metadata-边伪 GraphRAG）。

发现机制：`langflow.extensions` entry-point → `extension.json` → `components/liam/*`。

## 索引流水线（建库）

```text
Documents
  → Token Chunking → TextUnits
  → [standard] Entity/Rel Extract + Gleaning (+ optional Claims)
    or [fast] NLP noun phrases + co-occurrence (FastGraphRAG)
  → Hierarchical Leiden (fallback Louvain)
  → Community Reports (generate + summarize; fast 模式附原文片段)
  → link_provenance
  → Embeddings
  → Persist Knowledge Model
  → Ensure Vector Indexes (Astra $vector / Arango Faiss IVF+HNSW)
```

## 检索

| 模式 | 入口 | 数据加载 | 上下文 |
|------|------|----------|--------|
| Local | 实体 ANN（失败回退余弦） | **子图** `load_subgraph` | 邻域 + 原文 + citations |
| Global | 社区报告 | 报告集 | Map-Reduce |
| DRIFT | 报告 ANN Primer → Local 追问 | Primer 全量报告索引 + Local 子图 | 分层问答再汇总 |

向量检索默认 `use_vector_index=True`；`ann_fallback_exact` 控制失败是否回退精确余弦。

## 持久化集合（前缀 `{base}`）

- `{base}_documents` / `{base}_chunks`
- `{base}_entities` / `{base}_relationships`
- `{base}_communities` / `{base}_reports`
- `{base}_covariates`
- Arango：`{base}_entity_edges` + `{base}_kg_graph`

## 分层

```text
components/liam/*     UI（中文提示、参数校验）
graphrag/*            领域逻辑
```

## 与微软差异（诚实）

| 点 | 微软 | 本 Bundle |
|----|------|-----------|
| 标准 / Fast 建图 | 有 | ✅ |
| Local / Global / DRIFT | 有 | ✅ |
| 向量 ANN | 专用向量库 | ✅ Astra / Arango 后端 ANN |
| Prompt Tuning CLI | 有 | ❌ 用 Langflow 组件参数代替 |
| Prompt 文案 | 官方长英文包 | 中文导向精简模板（可替换） |

Arango 运维要求见根目录 [README.zh-CN.md](../README.zh-CN.md)。

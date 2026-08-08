# 架构说明

## 定位

`lfx-liam-bundle` 实现对齐微软 GraphRAG 默认 dataflow 的知识库扩展（非 metadata-边伪 GraphRAG）。

发现机制：`langflow.extensions` entry-point → `extension.json` → `components/liam/*`。

## 索引流水线（建库）

```text
Documents
  → TextUnits
  → Entity/Relationship Extraction + Data Gleaning
  → Description Summarization
  → Claim Extraction (optional)
  → Hierarchical Community Detection (Louvain)
  → Community Reports
  → link_provenance (Entity↔TextUnit↔Document 双向)
  → Embeddings (units / entities / reports)
  → Persist Knowledge Model (Astra / Arango)
```

持久化集合（前缀 `{base}`）：

- `{base}_documents` / `{base}_chunks`
- `{base}_entities` / `{base}_relationships`
- `{base}_communities` / `{base}_reports`
- `{base}_covariates`（可选 claims）
- Arango 另有 `{base}_entity_edges` 图边

## 检索

| 模式 | 入口 | 上下文 |
|------|------|--------|
| Local Search | 实体描述向量 | 邻域 + Entity-TextUnit Mapping 原文 + citations |
| Global Search | 社区报告 | Map 提取要点 → Reduce 汇总；可选动态社区剪枝 |

## 分层

```text
components/liam/*     UI 组件（中文提示、参数校验）
graphrag/*            领域逻辑（抽取/社区/报告/检索/存储）
```

原则：知识库实例为唯一边界；组件薄、逻辑厚；双后端共享同一 Knowledge Model。

## 溯源模型（对齐微软 data_model / 论文 provenance）

```text
Document.text_unit_ids  ←→  TextUnit.document_id
Entity.text_unit_ids    →   TextUnit
TextUnit.entity_ids     →   Entity          （反向）
TextUnit.relationship_ids / covariate_ids   （反向）
```

建库末段调用 `link_provenance()` 回填并持久化；Local Search 使用 Entity-TextUnit Mapping，
并输出 citations；组件「GraphRAG 溯源查询」暴露双向查询。

## 与微软实现的差异（诚实说明）

| 点 | 微软 | 本 Bundle |
|----|------|-----------|
| 社区算法 | Hierarchical Leiden (graspologic) | Hierarchical Louvain (networkx) |
| 默认存储 | Parquet + 向量库 | AstraDB / ArangoDB 文档集合 |
| Prompt | 官方长 prompt / 可调优 | 中文精简 prompt（可后续外置） |

结构阶段与检索语义对齐；算法依赖选择更轻量以便落地 Langflow。

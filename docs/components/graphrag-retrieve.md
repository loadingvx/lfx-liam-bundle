# GraphRAG 检索

| 项 | 值 |
|----|-----|
| 界面名称 | GraphRAG 检索 |
| 内部名称 | `LiamGraphRAGRetrieve` |
| 源码 | `components/liam/kb_retrieve.py` |
| 作用 | 对已建图知识库做 Local / Global / DRIFT 检索并生成答案或上下文 |

## 用途

三种检索模式：

| 模式 | 适用 | 依赖 |
|------|------|------|
| Local Search | 具体事实、实体相关问题 | Embedding；用 LLM 生成答案时需 LLM |
| Global Search | 主题级摘要、跨社区问题 | LLM |
| DRIFT Search | 社区 Primer + 多轮 Local 追问 | Embedding + LLM |

## 主要输入

| 参数 | 说明 |
|------|------|
| 知识库实例 | 已建图的实例 |
| Embedding 模型 | Local / DRIFT 必需；须与建库一致 |
| 语言模型 LLM | Global / DRIFT 必需；Local 用于生成答案 |
| 检索问题 | 用户问题 |
| 检索模式 | Local Search / Global Search / DRIFT Search |
| 对话历史 | 可选多轮上下文 |
| 回答形式 | 如「多段落中文回答」 |
| 上下文 token 预算 | 装配上下文总预算 |
| Local 原文/社区占比 | 预算分配（百分比） |
| Global 动态社区选择 / 允许通用知识 / Map 并发 / 社区层级 | Global 高级项 |
| DRIFT 追问轮数 / Primer 报告数 / 每轮最多追问 | DRIFT 高级项 |
| Local 实体数 / 原文片段数 | Local 召回规模 |
| Local 用 LLM 生成答案 | 关闭则主要返回上下文 |

## 输出

| 输出 | 说明 |
|------|------|
| 检索结果 | 结构化结果（含文档片段等） |
| 答案/上下文 | 自然语言答案或装配后的上下文 |

## 典型接线

```text
[知识库] ──┐
[Embedding]┼→ [GraphRAG 检索] → 答案
[LLM] ─────┘
```

## 注意点

- Embedding 与建库不一致会导致检索质量差或维度错误。  
- Local 健康时，结果 meta 常见 `vector_ranking=ann:*`、`index_load=subgraph`。  
- DRIFT 比 Local 更耗 LLM 调用次数，生产环境注意限流与成本。

## 相关文档

- [入库建图](graphrag-build.md)  
- [溯源查询](graphrag-provenance.md)  
- [最短 Flow](../guides/quickstart.md)

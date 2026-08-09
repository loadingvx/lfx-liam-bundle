# GraphRAG 入库建图

| 项 | 值 |
|----|-----|
| 界面名称 | GraphRAG 入库建图 |
| 内部名称 | `LiamGraphRAGBuild` |
| 源码 | `components/liam/kb_build.py` |
| 作用 | 将文档写入知识模型：切块、抽图、社区、报告、向量与 ANN |

## 用途

对「GraphRAG 知识库」实例执行完整索引流水线。支持两种建图模式：

- **标准 GraphRAG**：LLM 抽取实体/关系 + Gleaning（质量高、更贵）  
- **FastGraphRAG**：NLP 名词短语 + 共现（更快更便宜，图更噪，适合偏摘要）

随后做 Leiden 社区 → 社区报告 → 向量落库与 ANN 索引。

## 主要输入

| 参数 | 说明 |
|------|------|
| 知识库实例 | 连接「GraphRAG 知识库」输出 |
| 待入库文档 | `Data` / `DataFrame` / `Table` 列表 |
| Embedding 模型 | 必需；用于 TextUnit / 实体 / 报告向量化 |
| 语言模型 LLM | 必需；标准模式做抽取与报告，Fast 模式仍需写社区报告 |
| 建图模式 | 标准 GraphRAG / FastGraphRAG |
| 启用内置 token 切块 | 默认开；关闭则每条输入当作一个 TextUnit |
| 切块大小 / 重叠 | 默认约 1200 / 100 tokens |
| Gleaning 轮数 | 仅标准模式有效，建议 `1` |
| 抽取事实声明 Claims | 默认关；仅标准模式 |
| 社区最大规模 / 层数 | Leiden 相关高级参数 |
| 实体类型 | 标准模式抽取类型列表 |
| 写入模式 | 重建索引 / 追加合并 |

## 输出

| 输出 | 说明 |
|------|------|
| 知识库实例 | 建图后的同一实例（可继续接检索） |
| 建库汇总 | 文本单元、实体、社区、ANN 状态等摘要 |

## 典型接线

```text
[文档源] ──┐
[Embedding]┤
[LLM] ─────┼→ [GraphRAG 入库建图] → [GraphRAG 检索]
[知识库] ──┘
```

## 注意点

- 开启或修复 Arango 向量功能后，建议先做一次**重建索引**。  
- 汇总里应看到实体/社区/报告数量，并提示向量 ANN 就绪。  
- FastGraphRAG 对极短、无词组文本可能抽不到实体，可换更长文本或改用标准模式。

## 相关文档

- [知识库](graphrag-kb.md)  
- [检索](graphrag-retrieve.md)  
- [最短 Flow](../guides/quickstart.md)

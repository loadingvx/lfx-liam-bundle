# 最短可用 Flow

面向第一次把 GraphRAG 跑通的用户。

## 准备

| 后端 | 需要 |
|------|------|
| AstraDB | Endpoint、Token、前缀名；Embedding + LLM |
| ArangoDB | URL、库、账号密码、前缀名；向量索引已开启；Embedding + LLM |

## 步骤

1. **GraphRAG 知识库**  
   - 选后端，前缀例如 `liam_graphrag`  
   - 保持「启用向量库 ANN 检索」开启  
   - 运行至提示已连接  

2. **GraphRAG 入库建图**  
   - 接知识库实例、文档、Embedding、LLM  
   - 模式先选「标准 GraphRAG」或「FastGraphRAG」  
   - 写入模式选「重建索引」跑通一次  
   - 确认汇总里有实体/社区/报告，且 ANN 就绪  

3. **GraphRAG 检索**  
   - 同一知识库 + **同一 Embedding**  
   - 先用 Local Search 问一个具体问题  

可选：

- **GraphRAG 溯源查询**：用实体名或原文 ID 核对来源  
- **GraphRAG 知识库维护**：看统计；清空时确认语填 `确认清空`

## 接线示意

```text
[文档] ──┐
[Embed] ─┤
[LLM] ───┼→ [入库建图] → [检索] → 答案
[知识库] ┘
```

## 相关文档

- [知识库](../components/graphrag-kb.md)  
- [入库建图](../components/graphrag-build.md)  
- [检索](../components/graphrag-retrieve.md)  
- [Arango 排障](arango.md)

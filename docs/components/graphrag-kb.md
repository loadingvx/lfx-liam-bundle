# GraphRAG 知识库

| 项 | 值 |
|----|-----|
| 界面名称 | GraphRAG 知识库 |
| 内部名称 | `LiamGraphRAGKB` |
| 源码 | `components/liam/kb_instance.py` |
| 作用 | 创建或连接知识库实例；后续建图、检索、维护都围绕该实例 |

## 用途

选择存储后端（AstraDB / ArangoDB），配置连接信息与集合前缀，输出可被其它 GraphRAG 控件消费的「知识库实例」。

## 主要输入

| 参数 | 说明 |
|------|------|
| 存储后端 | `AstraDB` 或 `ArangoDB` |
| 知识库名称 | 界面显示名 |
| 知识库前缀名 | 存储前缀；会自动派生 `_chunks` / `_entities` 等集合。**不要**手写 `_chunks` 后缀 |
| 不存在则创建 | 目标集合不存在时是否自动创建 |
| Astra / Data API 相关 | Endpoint、Token、Keyspace、环境等（选 Astra 时） |
| Arango 相关 | URL、用户名、密码、数据库、图名称（选 Arango 时） |
| 启用向量库 ANN 检索 | 默认开启；用后端向量索引做近似检索 |
| ANN 失败回退精确余弦 | 向量检索不可用时是否回退 |
| Arango 向量索引 Factory | 高级；一般保持默认 |
| 向量相似度 | 默认 `cosine` |

## 输出

| 输出 | 说明 |
|------|------|
| 知识库实例 | `Data`，供入库建图 / 检索 / 维护 / 溯源连接 |

## 典型接线

```text
[GraphRAG 知识库] → 知识库实例 → [GraphRAG 入库建图]
                              → [GraphRAG 检索]
                              → [GraphRAG 知识库维护]
                              → [GraphRAG 溯源查询]
```

## 注意点

- 检索侧必须使用与建库时**相同前缀、同一数据库**的实例。  
- Arango 需开启向量索引能力，见 [../guides/arango.md](../guides/arango.md)。  
- 更换 Embedding 模型后应覆盖重建，避免向量维度不一致。

## 相关文档

- [入库建图](graphrag-build.md)  
- [检索](graphrag-retrieve.md)  
- [最短 Flow](../guides/quickstart.md)

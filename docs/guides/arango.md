# ArangoDB 环境与排障

使用 **ArangoDB** 作为 GraphRAG 存储后端时阅读本文。

## 服务器要求

| 要求 | 说明 |
|------|------|
| 版本 | ≥ 3.12.4（建议 3.12.6+） |
| 向量索引开关 | 3.12.4：`--experimental-vector-index true`；更高版本常见 `--vector-index` |
| 网络 | Langflow 能访问组件里填写的 Arango URL |
| 权限 | 账号可创建集合、图、索引 |

本地一键（可选）：

```bash
./devops/db-up.sh
./devops/test-integration.sh
./devops/db-down.sh
```

## 本模块会创建什么

以前缀 `{base}` 为例：

- 文档集合：`{base}_chunks` / `_entities` / `_relationships` / `_communities` / `_reports` / `_covariates` / `_documents`  
- 图：`{base}_kg_graph`，边集合 `{base}_entity_edges`  
- 入库后（ANN 开启）为实体描述、原文、社区报告等字段建立向量索引  

小样本时会自动调整索引参数，降低部分版本上的稳定性风险。

## 现象与处理

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| 创建向量索引失败 | 未开向量开关或版本过旧 | 开启开关后覆盖重建 |
| 近似检索失败 | 索引未建好 / 度量不一致 | ANN 开启后重建；度量先用 cosine |
| 提示 ANN 失败将回退精确余弦 | 建索引失败但允许回退 | 先修服务器；急用可暂靠回退 |
| 集合不存在 | 前缀/库名/账号不一致 | 与建库使用同一前缀与 database |
| 向量维度不一致 | 检索 Embedding ≠ 建库模型 | 换回原模型或覆盖重建 |
| 401 / 认证失败 | 用户名密码错 | 检查知识库组件凭证 |

## 最短自检

1. 从 Langflow 所在机器访问 Arango `_api/version`  
2. 确认向量索引功能已开启  
3. 知识库组件：地址/库/账号/前缀正确，ANN 开启  
4. 开启向量功能后做一次覆盖重建  
5. 检索结果 meta 中优先看到 ANN 与子图加载相关字段  

## 相关文档

- [知识库组件](../components/graphrag-kb.md)  
- [最短 Flow](quickstart.md)

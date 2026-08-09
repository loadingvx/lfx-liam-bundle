# 使用说明

面向「会打开 Langflow UI、但不想读源码」的用户。

## 你需要先准备什么

| 后端 | 你需要有 |
|------|----------|
| **AstraDB** | Astra API Endpoint、Token、知识库前缀名；Embedding + LLM |
| **ArangoDB** | Arango URL、数据库、用户名/密码、前缀名；**≥3.12.4 且开启 `--vector-index`**；Embedding + LLM |

完整 GraphRAG：

- LLM：标准建图抽取 / 社区报告 / Global / DRIFT；FastGraphRAG 仍需 LLM 写社区报告
- Embedding：向量化 + Local / DRIFT

入库默认会 **按 token 自动切块**（约 1200，可关）。

## 最短可用 Flow

1. **GraphRAG 知识库**  
   - 选 AstraDB / ArangoDB  
   - 前缀名填 `liam_graphrag`（不要加 `_chunks`）  
   - **保持「启用向量库 ANN 检索」开启**  
   - Arango：确认服务器已开 `--vector-index`（详见 [README.zh-CN.md](../README.zh-CN.md) 排障表）  
   - 运行，确认提示「已连接 / 可开始入库建图」
2. **GraphRAG 入库建图**  
   - 接入 KB、文档、Embedding、LLM  
   - 建图模式：  
     - **标准 GraphRAG**：质量优先（贵）  
     - **FastGraphRAG**：NLP 共现，更快更便宜，适合偏 Global 摘要  
   - Gleaning 建议 `1`（仅标准模式有效）  
   - **覆盖重建**一次（尤其刚打开 Arango 向量功能后）  
   - 成功汇总应含实体/社区/报告，并提示 `向量ANN=就绪`
3. **GraphRAG 检索**  
   - 接同一 KB + **同一 Embedding**  
   - **Local**：具体问题；meta 里 `vector_ranking=ann:*`、`index_load=subgraph` 为健康  
   - **Global**：主题问题，必须 LLM  
   - **DRIFT**：社区 Primer + 多轮 Local 追问（要 Embedding+LLM；可调追问轮数）

维护用 **GraphRAG 知识库维护**：统计直接看；清空必须在确认语输入 `确认清空`。

## 溯源（实体 ↔ 原文）

1. 入库写入双向链接：`实体.text_unit_ids` ↔ `文本单元.entity_ids`
2. Local / DRIFT 答案可带来源线索
3. 用 **GraphRAG 溯源查询** 核对实体/原文/文档

## 常见报错

| 现象 | 可能原因 | 怎么做 |
|------|----------|--------|
| 面板找不到 GraphRAG | 扩展未装入环境 | `./scripts/deploy-to-docker.sh` 后硬刷新 |
| 建库失败：未连接 LLM | 入库未接语言模型 | 接任意 LanguageModel |
| FastGraphRAG 无实体 | 文本无可用词组 | 换更长文本，或改用标准模式 |
| 未能抽取到任何实体 | LLM 不可用或文本无信息量 | 检查模型；提高 Gleaning；换更长文本 |
| Local 报无实体 | 尚未建图或前缀不一致 | 先入库；确认检索接同一 KB |
| 向量维度不一致 | 检索 Embedding 与建库不同 | 换回原模型，或覆盖重建 |
| Arango 向量索引失败 | 未开 `--vector-index` / 版本低 | 见 README 排障表；修好后覆盖重建 |
| Astra 不是向量集合 | 旧库为普通集合 | 覆盖重建入库 |
| DRIFT 必须连接 LLM/Embedding | 缺模型 | 两个都接上 |
| Global 无社区报告 | 建图未完成 | 重新入库，确认有 reports |
| 清空被拒绝 | 确认语不对 | 精确输入：`确认清空` |

## 生产环境建议

1. 固定版本安装：`pip install lfx-liam-bundle==x.y.z`
2. 密钥走环境变量 / 密钥管理
3. 大语料：先小样本验证 Flow；偏摘要可试 FastGraphRAG；偏精确实体用标准模式
4. Claims 默认关闭；需要事实声明时再开（标准模式）
5. Arango 生产务必先开 vector-index 再全量建库

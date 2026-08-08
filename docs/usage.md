# 使用说明

面向「会打开 Langflow UI、但不想读源码」的用户。

## 你需要先准备什么

| 后端 | 你需要有 |
|------|----------|
| **AstraDB** | Astra API Endpoint、Token、知识库前缀名；Embedding + LLM |
| **ArangoDB** | Arango URL、数据库、用户名/密码、前缀名；Embedding + LLM |

完整 GraphRAG **必须同时有 LLM 和 Embedding**：

- LLM：实体/关系抽取、Data Gleaning、社区报告、Global Search
- Embedding：TextUnit / 实体描述 / 报告向量，以及 Local Search

## 最短可用 Flow

1. **GraphRAG 知识库**  
   - 选 AstraDB / ArangoDB  
   - 前缀名填 `liam_graphrag`（不要加 `_chunks`）  
   - 运行，确认提示「已连接 / 可开始入库建图」
2. **GraphRAG 入库建图**  
   - 接入 KB 实例、切分后的文档、Embedding、LLM  
   - Gleaning 轮数建议 `1`  
   - 运行成功后应看到实体/关系/社区/报告数量
3. **GraphRAG 检索**  
   - 接同一 KB 实例  
   - **Local Search**：具体「谁/什么/哪里」问题 → 需 Embedding（建议再接 LLM 出答案）  
   - **Global Search**：主题/全局总结 → 必须接 LLM；可选「动态社区选择」

维护用 **GraphRAG 知识库维护**：统计直接看；清空必须在确认语输入 `确认清空`。

## 溯源（实体 ↔ 原文）

微软 GraphRAG / 论文强调 **provenance**：答案要能回到源文本。

1. 建库时会自动写双向链接：`实体.text_unit_ids` 与 `文本单元.entity_ids`
2. Local Search 答案末尾会附「可核对原文出处」
3. 用 **GraphRAG 溯源查询**：
   - `实体 → 原文`：填实体名，看它来自哪些片段
   - `原文 → 实体`：填 TextUnit ID（如检索结果里的 `[xxx]`）
   - `文档 → 图元素`：按文档聚合实体
   - 旧库缺反向字段时，选 `重建双向索引`

## 常见报错

| 现象 | 可能原因 | 怎么做 |
|------|----------|--------|
| 面板找不到 GraphRAG | 扩展未装入环境 | `./scripts/deploy-to-docker.sh` 后硬刷新 |
| 建库失败：未连接 LLM | 入库未接语言模型 | 接任意 LanguageModel |
| 未能抽取到任何实体 | LLM 不可用或文本无信息量 | 检查模型；提高 Gleaning；换更长文本 |
| Local Search 报无实体 | 尚未建图或集合前缀不一致 | 先跑入库；确认检索接同一 KB |
| Global Search 无社区报告 | 建图未完成社区阶段 | 重新入库建图，确认汇总里有 communities/reports |
| 清空被拒绝 | 确认语不对 | 精确输入：`确认清空` |

## 生产环境建议

1. 固定版本安装：`pip install lfx-liam-bundle==0.3.0`
2. 密钥走环境变量 / 密钥管理
3. 大语料建库耗时长且费 LLM：先小样本验证 Flow，再全量
4. Claims 抽取默认关闭（与微软一致）；需要事实声明时再开

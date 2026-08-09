# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[English](README.md)

对齐 [微软 GraphRAG 默认 dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/) 的完整 GraphRAG Langflow Extension。

后端：**AstraDB**、**ArangoDB**。

## 能力一览

| 阶段 | 能力 |
|------|------|
| 建库 | 内置 token 切块（默认 1200 / overlap 100） |
| 建库 | **标准 GraphRAG**：LLM 实体/关系 + Gleaning |
| 建库 | **FastGraphRAG**：NLP 名词短语 + 共现（更快更便宜，图更噪） |
| 建库 | 分层 Leiden 社区；社区报告；可选 Claims |
| 建库 | 双向溯源；向量落库 + **后端 ANN 索引（默认开）** |
| 检索 | Local（ANN 实体入口 + **子图加载**） |
| 检索 | Global Map-Reduce |
| 检索 | **DRIFT**（社区 Primer + Local 追问迭代） |

## 组件

建库：知识库 / 入库建图；检索（Local/Global/DRIFT）；维护；溯源查询。

## 安装

```bash
pip install lfx-liam-bundle
# 或
./scripts/deploy-to-docker.sh
```

Python **3.10+**。UI 搜索 `GraphRAG` / `Liam`。

## ArangoDB 环境要求与排障（必读）

选 Arango 时，先按本表排查，再改 Flow。

### 服务器要求

| 要求 | 原因 |
|------|------|
| ArangoDB **≥ 3.12.4**（建议 **3.12.6+**） | 向量索引与 `APPROX_NEAR_*` |
| 启动开启向量索引 | 3.12.4：`--experimental-vector-index true`；更高版本可能是 `--vector-index` |
| Langflow 能访问 `arango_url` | 否则连接超时 |
| 账号具备建集合 / 图 / 索引权限 | 否则骨架或 ANN 失败 |

```bash
# 3.12.4
arangod --experimental-vector-index true
# 更高版本常见：
# arangod --vector-index true
```

本地一键（推荐）：

```bash
./devops/db-up.sh              # compose 起 Arango :18529 + 向量索引
./devops/test-integration.sh   # 真库集成测试
./devops/db-down.sh
```

> 开启后会永久改变该部署的存储布局（额外 RocksDB column family），生产环境请提前规划。  
> 小样本（<40 文档）本 Bundle 会自动用 `IVF{n},Flat` 而非 HNSW，避免 Arango 3.12.4 Faiss 崩溃。

### 本 Bundle 在 Arango 上会做什么

1. 创建 `{前缀}_chunks/_entities/_relationships/_communities/_reports/_covariates/_documents`
2. 创建图 `{前缀}_kg_graph` 与边集合 `{前缀}_entity_edges`
3. 入库后（ANN 开启）为实体/原文/报告字段建 Faiss 向量索引  
   默认 factory 模板 `IVF100_HNSW10,Flat`（IVF+HNSW）；**IVF 基数会按文档数自动收缩**，小库不会硬套 100
4. Local/DRIFT 用 AQL `APPROX_NEAR_COSINE`（或 l2 / innerProduct）做近似检索

### 现象 → 原因 → 处理

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| 提示「创建向量索引失败」/ unknown vector | 未开实验/正式向量开关或版本过旧 | 开启 `--experimental-vector-index`（或 `--vector-index`），再**覆盖重建** |
| Arango 进程 SIGSEGV / 容器 Exit 139 | 极小样本 + HNSW factory（旧版本 bug） | 升级 Bundle（小库自动降级 Flat）；或换更新 Arango |
| `APPROX_NEAR_*` 查询失败 | 索引未建好 / 度量不一致 | ANN 开启后重建；度量先用 `cosine` |
| 汇总出现「向量ANN=失败(将回退精确余弦)」 | 建索引失败但允许回退 | 先修 Arango；急用可暂靠回退 |
| ANN 直接报错不回退 | 关掉了「ANN 失败回退精确余弦」 | 打开回退，或先修好 Arango |
| 集合不存在 | 前缀/库名/账号不一致 | 与建库同一前缀与 database；开启「不存在则创建」 |
| 检索慢，但 ANN 显示就绪 | 子图加载失败回退全量 | 看检索 meta 的 `index_load`：`subgraph` / `full` |
| 向量维度不一致 | 检索 Embedding ≠ 建库模型 | 换回原模型，或覆盖重建 |
| 401 / 认证失败 | 用户名密码错 | 检查知识库组件凭证 |
| 小库建索引异常 | nLists 过大（少见） | 升级 Bundle 后重建（会自动收缩 nLists） |

### Arango 最短自检清单

1. 从 Langflow 所在机器访问 `http://主机:8529/_api/version`  
2. 确认已开 `--vector-index`  
3. 知识库组件：地址/库/账号/前缀正确，**启用向量库 ANN 检索=开**  
4. 开启向量功能后做一次**覆盖重建**入库  
5. 检索 meta 期望：`vector_ranking=ann:arangodb`，`index_load=subgraph`

## 与微软实现的差异

| 主题 | 微软 | 本 Bundle |
|------|------|-----------|
| 标准抽取 | LLM + Gleaning | ✅ |
| FastGraphRAG | NLP 名词 + 共现 | ✅（轻量正则 NLP，不强制 spaCy） |
| Local / Global / DRIFT | 官方引擎 | ✅ 三种都有（中文导向精简 prompt） |
| 向量 ANN | 专用向量库 | ✅ Astra `$vector` / Arango Faiss IVF(+HNSW) |
| ANN 后局部加载 | 向量库 + 选择性取数 | ✅ `load_subgraph` |
| Prompt Tuning **CLI** | 独立 CLI | ❌ **有意不做**：在 Langflow 用组件参数调；长英文官方 prompt 可自行替换 `graphrag/*` 内模板 |

## 文档

- [使用说明](docs/usage.md)
- [架构说明](docs/architecture.md)
- [开发指南](docs/development.md)

## 许可证

[MIT](LICENSE)

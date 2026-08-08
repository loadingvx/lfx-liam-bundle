# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[English](README.md)

**完整 GraphRAG**（对齐 [微软 GraphRAG 默认 dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/)）的 Langflow Extension：以知识库实例为边界，建库侧完成抽取/社区/报告，检索侧提供 Local Search 与 Global Search。

后端支持：**AstraDB**、**ArangoDB**。

## 与「真正 GraphRAG」对齐的能力

| 阶段 | 能力 | 本 Bundle |
|------|------|-----------|
| 建库 | TextUnit 组合 | ✅ |
| 建库 | 实体 + 关系抽取 | ✅ |
| 建库 | Data Gleaning 多轮补抽 | ✅ |
| 建库 | 描述合并摘要 | ✅ |
| 建库 | Claims/Covariates（可选） | ✅（默认关） |
| 建库 | 分层社区检测 | ✅（Hierarchical Louvain；微软默认 Leiden） |
| 建库 | 社区报告 | ✅ |
| 建库 | TextUnit / 实体 / 报告向量化 | ✅ |
| 检索 | Local Search | ✅ |
| 检索 | Global Search Map-Reduce | ✅ |
| 检索 | 动态社区选择 | ✅（可选） |
| 溯源 | Entity↔TextUnit↔Document 双向链接 + 引用出处 | ✅ |

## 组件

| 侧 | 组件 | 作用 |
|----|------|------|
| 建库 | **GraphRAG 知识库** | 创建/连接实例，初始化知识模型集合 |
| 建库 | **GraphRAG 入库建图** | 完整索引流水线（需 LLM + Embedding） |
| 检索 | **GraphRAG 检索** | Local Search / Global Search |
| 维护 | **GraphRAG 知识库维护** | 统计 / 清空（需确认语） |
| 溯源 | **GraphRAG 溯源查询** | 实体↔原文↔文档 双向核对 |

## 推荐 Flow

```text
文档切分 ──► GraphRAG 入库建图 ◄── Embedding
                ▲         ▲
         GraphRAG 知识库   LLM
                │
                ▼
         GraphRAG 检索 ──► 答案/上下文
              ▲
         Embedding + LLM（按模式）
```

1. 配置「GraphRAG 知识库」（AstraDB 或 ArangoDB；前缀名如 `liam_graphrag`）
2. 「入库建图」接入文档、Embedding、LLM；设置 Gleaning 轮数
3. 「GraphRAG 检索」选 Local（具体实体问题）或 Global（主题/全局问题）

## 安装

```bash
pip install lfx-liam-bundle
# 或
./scripts/deploy-to-docker.sh
```

UI：Components 搜索 `GraphRAG` / `Liam`。

## 依赖

- `networkx`：分层社区
- Astra：`astrapy`
- Arango：`python-arango`
- `lfx>=1.11,<2`

## 文档

- [使用说明](docs/usage.md)
- [架构说明](docs/architecture.md)
- [开发指南](docs/development.md)
- 官方 GraphRAG：[Indexing Dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/) /
  [Local Search](https://microsoft.github.io/graphrag/query/local_search/) /
  [Global Search](https://microsoft.github.io/graphrag/query/global_search/)

## 许可证

[MIT](LICENSE)

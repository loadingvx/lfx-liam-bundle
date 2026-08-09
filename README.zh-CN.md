# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[English](README.md)

这是 Liam 的 **Langflow 扩展工具包**（bundle 名：`liam`）：按「个人组件库」方式持续扩展，而不是单一功能产品。当前已内置 GraphRAG 相关控件，后续还会在同一工具包下增加其它组件。

## 工程架构

```text
langflow.extensions 入口
  └─ lfx_liam_bundle / extension.json
       └─ bundle：liam
            └─ components/liam/*     # Langflow 界面控件
       └─ 领域包（例如 graphrag/*）  # 控件背后的可复用逻辑
```

| 层级 | 职责 |
|------|------|
| `extension.json` | 扩展标识、展示名、bundle 注册 |
| `components/liam/` | Langflow 控件（参数、校验、英文界面文案） |
| 领域包 | 与 UI 解耦的业务实现（目前主要是 `graphrag/`） |

新能力优先以**新控件**（必要时加新领域包）接入同一 `liam` bundle，不必都做成 GraphRAG。

## 当前支持的 Langflow 控件

界面名称与帮助文案为**英文**（与 Langflow UI 一致）：

| 控件（Display name） | 作用 |
|----------------------|------|
| GraphRAG Knowledge Base | 创建或连接知识库实例（AstraDB / ArangoDB） |
| GraphRAG Index Builder | 文档入库、建图、写社区报告 |
| GraphRAG Retrieve | Local / Global / DRIFT 检索 |
| GraphRAG Maintain | 规模统计、清空（危险操作，确认语 `CONFIRM DELETE`） |
| GraphRAG Provenance | 实体 ↔ 原文片段双向溯源 |

安装后在 Langflow 中打开 **Liam** 分组，或搜索 `GraphRAG` / `Liam`。

## 安装

```bash
pip install lfx-liam-bundle
```

需要 Python **3.10+**。由 Langflow 通过 `langflow.extensions` 入口自动发现扩展（参见 [Langflow Extensions](https://docs.langflow.org/extensions-quickstart)）。

写入本机 Langflow Docker（可选）：

```bash
./scripts/deploy-to-docker.sh
```

## GraphRAG 模块说明

GraphRAG 是本工具包**当前已提供**的一组控件与领域库，能力包括：标准 / Fast 建图、分层社区、Local / Global / DRIFT 检索，以及 AstraDB、ArangoDB 上的向量 ANN。

详细说明（按组件维护）：**[docs/index.md](docs/index.md)**

- 工具包总览：[docs/overview.md](docs/overview.md)  
- 最短 Flow：[docs/guides/quickstart.md](docs/guides/quickstart.md)  
- Arango 排障：[docs/guides/arango.md](docs/guides/arango.md)

上游概念可参考 [Microsoft GraphRAG](https://microsoft.github.io/graphrag/)。

## 本地开发

```bash
mise exec -- uv sync
mise exec -- uv run pytest -m "not integration"
./devops/db-up.sh && ./devops/test-integration.sh   # 可选：真库集成
```

安装与接入详见 [docs/guides/install.md](docs/guides/install.md)。

## 许可证

[MIT](LICENSE)

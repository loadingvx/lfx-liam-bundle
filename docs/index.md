# lfx-liam-bundle 文档

本仓库是 **Liam 的 Langflow 扩展工具包**（bundle：`liam`）。  
文档按「工具包总览 → 组件说明 → 通用指南」组织，新增组件时在 `components/` 下补一篇即可。

## 目录结构

```text
docs/
  index.md                 # 本页：汇总入口
  overview.md              # 工具包架构与约定
  components/              # 每个 Langflow 控件一篇说明
    graphrag-kb.md
    graphrag-build.md
    graphrag-retrieve.md
    graphrag-maintain.md
    graphrag-provenance.md
  guides/                  # 跨组件的安装、搭 Flow、运维
    install.md
    quickstart.md
    arango.md
```

## 当前组件

| 界面名称 | 内部类名 | 说明文档 |
|----------|----------|----------|
| GraphRAG 知识库 | `LiamGraphRAGKB` | [components/graphrag-kb.md](components/graphrag-kb.md) |
| GraphRAG 入库建图 | `LiamGraphRAGBuild` | [components/graphrag-build.md](components/graphrag-build.md) |
| GraphRAG 检索 | `LiamGraphRAGRetrieve` | [components/graphrag-retrieve.md](components/graphrag-retrieve.md) |
| GraphRAG 知识库维护 | `LiamGraphRAGMaintain` | [components/graphrag-maintain.md](components/graphrag-maintain.md) |
| GraphRAG 溯源查询 | `LiamGraphRAGProvenance` | [components/graphrag-provenance.md](components/graphrag-provenance.md) |

## 指南

| 文档 | 内容 |
|------|------|
| [overview.md](overview.md) | 工具包分层、扩展方式 |
| [guides/install.md](guides/install.md) | 安装与装入 Langflow |
| [guides/quickstart.md](guides/quickstart.md) | 最短可用 Flow |
| [guides/arango.md](guides/arango.md) | ArangoDB 环境与排障 |

## 维护约定

1. **每新增一个 Langflow 控件**：在 `docs/components/` 增加一篇 md，并在本页「当前组件」表追加一行。  
2. **组件文档建议结构**：用途 → 输入/输出 → 典型接线 → 注意点 → 相关文档。  
3. **跨组件事项**（安装、数据库运维）放 `guides/`，不要复制进每个组件页。  
4. 根目录 [README.md](../README.md) / [README.zh-CN.md](../README.zh-CN.md) 只做总览，详细说明以本目录为准。

# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[中文文档](README.zh-CN.md)

A Langflow Extension that implements **full GraphRAG** aligned with the
[Microsoft GraphRAG default dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/).
Indexing builds entities, communities, and reports around a knowledge-base instance;
query supports Local Search and Global Search.

Backends: **AstraDB**, **ArangoDB**.

## Capabilities

| Stage | Capability | This bundle |
|-------|------------|-------------|
| Index | TextUnit composition | ✅ |
| Index | Entity + relationship extraction | ✅ |
| Index | Data Gleaning | ✅ |
| Index | Description summarization | ✅ |
| Index | Claims / Covariates (optional) | ✅ (off by default) |
| Index | Hierarchical communities | ✅ (Louvain; Microsoft uses Leiden) |
| Index | Community reports | ✅ |
| Index | Embeddings for units / entities / reports | ✅ |
| Query | Local Search | ✅ |
| Query | Global Search (map-reduce) | ✅ |
| Query | Dynamic community selection | ✅ (optional) |
| Provenance | Entity ↔ TextUnit ↔ Document + citations | ✅ |

## Components

| Side | Component | Role |
|------|-----------|------|
| Build | **GraphRAG Knowledge Base** | Create / connect instance and schema |
| Build | **GraphRAG Index Builder** | Full indexing pipeline (LLM + Embedding required) |
| Query | **GraphRAG Retrieve** | Local Search / Global Search |
| Ops | **GraphRAG Maintain** | Stats / clear (confirmation required) |
| Provenance | **GraphRAG Provenance** | Entity ↔ source text ↔ document lookup |

## Recommended flow

```text
Split docs ──► GraphRAG Index Builder ◄── Embedding
                    ▲           ▲
         GraphRAG Knowledge Base   LLM
                    │
                    ▼
             GraphRAG Retrieve ──► answer / context
                    ▲
           Embedding + LLM (by mode)
```

1. Configure **GraphRAG Knowledge Base** (AstraDB or ArangoDB; prefix e.g. `liam_graphrag`).
2. Wire documents, Embedding, and LLM into **Index Builder**; set Gleaning rounds.
3. Use **Retrieve**: Local for entity-centric questions, Global for thematic / corpus-wide questions.

## Install

```bash
pip install lfx-liam-bundle
# or local docker Langflow:
./scripts/deploy-to-docker.sh
```

In the UI, search Components for `GraphRAG` / `Liam`.

## Dependencies

- `networkx` — hierarchical communities
- `astrapy` — AstraDB
- `python-arango` — ArangoDB
- `lfx>=1.11,<2`

## Docs

- [Usage](docs/usage.md) (Chinese)
- [Architecture](docs/architecture.md) (Chinese)
- [Development](docs/development.md) (Chinese)
- Upstream GraphRAG: [Indexing](https://microsoft.github.io/graphrag/index/default_dataflow/) ·
  [Local Search](https://microsoft.github.io/graphrag/query/local_search/) ·
  [Global Search](https://microsoft.github.io/graphrag/query/global_search/)

## License

[MIT](LICENSE)

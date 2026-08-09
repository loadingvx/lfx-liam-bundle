# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[中文说明](README.zh-CN.md)

Personal **Langflow extension toolkit** (`liam` bundle): a growing set of UI components and shared libraries for Liam’s Langflow workflows. GraphRAG is one capability shipped today—not the whole product.

## Architecture

```text
langflow.extensions entry-point
  └─ lfx_liam_bundle / extension.json
       └─ bundle: liam
            └─ components/liam/*     # Langflow UI components
       └─ domain packages (e.g. graphrag/*)
```

| Layer | Role |
|-------|------|
| `extension.json` | Extension id, display name, bundle registration |
| `components/liam/` | Langflow components (inputs, validation, Chinese UI copy) |
| Domain packages | Reusable logic behind components (currently `graphrag/`) |

New tools should land as new components (and optional domain packages) under the same `liam` bundle—without forcing every feature into GraphRAG.

## Components (current)

| Component (UI) | Purpose |
|----------------|---------|
| GraphRAG 知识库 | Create / connect a GraphRAG KB (AstraDB or ArangoDB) |
| GraphRAG 入库建图 | Index documents into the knowledge model |
| GraphRAG 检索 | Local / Global / DRIFT search |
| GraphRAG 知识库维护 | Stats and clear (dangerous) |
| GraphRAG 溯源查询 | Entity ↔ TextUnit provenance lookup |

In the Langflow UI, open the **Liam** bundle or search for `GraphRAG` / `Liam`.

## Install

```bash
pip install lfx-liam-bundle
```

Requires Python **3.10+**. Runtime discovery uses the `langflow.extensions` entry-point (see [Langflow Extensions](https://docs.langflow.org/extensions-quickstart)).

Deploy into a local Langflow Docker container (optional):

```bash
./scripts/deploy-to-docker.sh
```

## GraphRAG module (summary)

Current GraphRAG support covers indexing (standard / FastGraphRAG), hierarchical communities, Local / Global / DRIFT retrieve, and vector ANN on AstraDB / ArangoDB.

Full docs (Chinese, component-by-component): **[docs/index.md](docs/index.md)**  
Upstream concepts: [Microsoft GraphRAG](https://microsoft.github.io/graphrag/)

## Development

```bash
mise exec -- uv sync
mise exec -- uv run pytest -m "not integration"
./devops/db-up.sh && ./devops/test-integration.sh   # optional real DB
```

See [docs/guides/install.md](docs/guides/install.md).

## License

[MIT](LICENSE)

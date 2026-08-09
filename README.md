# lfx-liam-bundle

[![Publish](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml/badge.svg)](https://github.com/loadingvx/lfx-liam-bundle/actions/workflows/python-publish.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![LFX Extension](https://img.shields.io/badge/langflow-extension-0ea5e9.svg)](https://docs.langflow.org/extensions-quickstart)

[中文文档](README.zh-CN.md)

A Langflow Extension implementing **full GraphRAG** aligned with the
[Microsoft GraphRAG default dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/).

Backends: **AstraDB**, **ArangoDB**.

## What you get

| Stage | Capability |
|-------|------------|
| Index | Token chunking (default 1200 / overlap 100) → TextUnits |
| Index | **Standard**: LLM entity/relationship + Data Gleaning |
| Index | **FastGraphRAG**: NLP noun phrases + co-occurrence (cheaper/noisier) |
| Index | Hierarchical **Leiden** communities (+ Louvain fallback) |
| Index | Community reports (generate + summarize); optional Claims |
| Index | Embeddings + bidirectional provenance |
| Index | Backend **vector ANN** indexes (default on) |
| Query | Local Search (ANN entity entry + **subgraph load**) |
| Query | Global Search map-reduce |
| Query | **DRIFT Search** (community primer + local follow-ups) |

## Components

| Side | Component |
|------|-----------|
| Build | GraphRAG Knowledge Base / Index Builder |
| Query | GraphRAG Retrieve (Local / Global / DRIFT) |
| Ops | GraphRAG Maintain |
| Provenance | GraphRAG Provenance |

## Install

```bash
pip install lfx-liam-bundle
# or into local Langflow docker:
./scripts/deploy-to-docker.sh
```

Python **3.10+**. Search UI for `GraphRAG` / `Liam`.

## ArangoDB requirements & troubleshooting

If you choose **ArangoDB**, read this before blaming the Flow.

### Server requirements

| Requirement | Why |
|-------------|-----|
| ArangoDB **≥ 3.12.4** (**3.12.6+** recommended) | Vector AQL + index APIs |
| Vector index startup flag | `3.12.4`: `--experimental-vector-index true`; newer may use `--vector-index` |
| Network reachability from Langflow to `arango_url` | Connection / timeout errors otherwise |
| User with rights to create collections, graphs, indexes | Schema + ANN setup |

Enable vector indexes (examples):

```bash
arangod --experimental-vector-index true   # 3.12.4
# arangod --vector-index true              # newer builds
```

Local one-liner:

```bash
./devops/db-up.sh
./devops/test-integration.sh   # real DB tests (Arango required; Astra if env set)
./devops/db-down.sh
```

> Enabling vector indexes permanently changes storage layout. Tiny corpora (<40 docs) use `IVF{n},Flat` automatically (HNSW can SIGSEGV on Arango 3.12.4).

### What this bundle does on Arango

1. Creates document collections: `{prefix}_chunks/_entities/_relationships/_communities/_reports/_covariates/_documents`
2. Creates graph `{prefix}_kg_graph` with `{prefix}_entity_edges`
3. After indexing (ANN on): creates Faiss **vector indexes** on
   - `entities.description_embedding`
   - `chunks.embedding`
   - `reports.embedding`
4. Default factory template: `IVF100_HNSW10,Flat` — IVF base + HNSW; **IVF list count is auto-shrunk** to fit document count (small corpora will not use literal `IVF100`)
5. Local/DRIFT entity/report entry uses AQL `APPROX_NEAR_COSINE` (or L2 / innerProduct)

### Symptom → check → fix

| Symptom (UI / log) | Likely cause | What to do |
|--------------------|--------------|------------|
| Vector index create fails / unknown type | Flag off or old version | Enable `--experimental-vector-index` / `--vector-index`; rebuild |
| Arango Exit 139 / SIGSEGV on index create | Tiny corpus + HNSW factory | Upgrade this bundle (auto Flat for <40 docs) or newer Arango |
| `APPROX_NEAR_*` AQL error | No vector index, or metric mismatch | Rebuild with ANN on; keep metric=`cosine` unless you know you need l2/IP |
| `向量ANN=失败(将回退精确余弦)` | Index create failed but fallback allowed | Fix server (above); or temporarily rely on fallback |
| ANN 直接报错、不回退 | “ANN 失败回退精确余弦” turned **off** | Turn it back on, or fix Arango first |
| `集合不存在` | Wrong prefix / DB / user | Same `知识库前缀名` + database as build; toggle “不存在则创建” |
| Local 慢但 ANN 显示 ready | Subgraph path fell back to full load | Check `index_load` in retrieve meta (`subgraph` vs `full`) |
| 维度不一致 | Different Embedding model than build | Use the **same** Embedding; or rebuild with overwrite |
| 认证失败 / 401 | Wrong user/password | Fix Arango credentials on KB component |
| 小库建索引怪错 | `nLists` > doc count (should be rare) | Rebuild; bundle auto-shrinks nLists — upgrade bundle if old |

### Minimal Arango checklist

1. `curl -s http://<host>:8529/_api/version` works from Langflow host  
2. Vector feature enabled (`--vector-index`)  
3. KB component: URL / DB / user / password / prefix correct; **启用向量库 ANN 检索=开**  
4. Build with **覆盖重建** once after enabling vector feature  
5. Retrieve meta should show `vector_ranking=ann:arangodb` and preferably `index_load=subgraph`

## Differences vs Microsoft GraphRAG

| Topic | Microsoft GraphRAG | This bundle |
|-------|--------------------|-------------|
| Chunking | Built-in token chunks | ✅ |
| Standard extract | LLM + gleaning | ✅ |
| FastGraphRAG index | NLP nouns + co-occurrence | ✅ (lightweight regex NLP; no spaCy required) |
| Communities | Hierarchical Leiden | ✅ Leiden (+ Louvain fallback) |
| Local / Global / DRIFT | Official engines | ✅ All three (compact Chinese-oriented prompts) |
| Context budget | Token packing | ✅ tiktoken |
| Vector ANN | Dedicated vector store | ✅ Astra `$vector` / Arango Faiss IVF(+HNSW) |
| Subgraph load after ANN | Vector store + selective load | ✅ `load_subgraph` after ANN seeds |
| Prompt-tuning **CLI** | `graphrag` CLI / prompt tune | ❌ Intentionally omitted — tune via Langflow component params + prompts in code |

### Prompt / CLI note

Microsoft’s **prompt-tuning CLI** is a standalone repo workflow. This extension runs inside Langflow: response type, history, budgets, DRIFT depth, indexing mode, ANN toggles are **component inputs**. Full CLI parity is not a goal; if you need Microsoft’s exact long English prompt packs, fork and replace prompt strings under `graphrag/*`.

## Docs

- [Usage](docs/usage.md) (Chinese)
- [Architecture](docs/architecture.md) (Chinese)
- [Development](docs/development.md) (Chinese)
- Upstream: [Indexing](https://microsoft.github.io/graphrag/index/default_dataflow/) ·
  [Local](https://microsoft.github.io/graphrag/query/local_search/) ·
  [Global](https://microsoft.github.io/graphrag/query/global_search/) ·
  [DRIFT](https://microsoft.github.io/graphrag/query/drift_search/) ·
  [Methods / FastGraphRAG](https://microsoft.github.io/graphrag/index/methods/)

## License

[MIT](LICENSE)

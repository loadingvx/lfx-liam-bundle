# ArangoDB setup and troubleshooting

Read this when using **ArangoDB** as the GraphRAG storage backend.

## Server requirements

| Requirement | Notes |
|-------------|-------|
| Version | ≥ 3.12.4 (prefer 3.12.6+) |
| Vector index flag | 3.12.4: `--experimental-vector-index true`; newer builds often use `--vector-index` |
| Network | Langflow must reach the Arango URL configured in the component |
| Permissions | Account can create collections, graphs, and indexes |

Local one-shot (optional):

```bash
./devops/db-up.sh
```

## What this module creates

With prefix `{base}`:

- Document collections: `{base}_chunks` / `_entities` / `_relationships` / `_communities` / `_reports` / `_covariates` / `_documents`  
- Graph: `{base}_kg_graph`, edge collection `{base}_entity_edges`  
- After indexing (ANN on): vector indexes on entity descriptions, text units, community reports, etc.

Small corpora auto-tune index parameters to reduce stability risk on some versions.

## Symptoms and fixes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Vector index create fails | Flag off or version too old | Enable flag, then rebuild |
| Approximate search fails | Index missing / metric mismatch | Rebuild with ANN on; use cosine first |
| ANN failed; falling back to exact cosine | Index failed but fallback allowed | Fix server; fallback is temporary |
| Collection missing | Wrong prefix / DB / credentials | Match the KB component settings |
| Embedding dimension mismatch | Retrieve Embedding ≠ indexing model | Restore original model or rebuild |
| 401 / auth failure | Bad username/password | Fix credentials on Knowledge Base |

## Quick self-check

1. From the Langflow host, hit Arango `_api/version`  
2. Confirm vector-index support is enabled  
3. Knowledge Base: URL / database / credentials / prefix correct; ANN on  
4. Rebuild once after enabling vectors  
5. Prefer seeing ANN / subgraph fields in retrieve meta  

## Related

- [Knowledge Base](../components/graphrag-kb.md)  
- [Quickstart](quickstart.md)

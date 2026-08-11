# GraphRAG Knowledge Base

| Item | Value |
|------|-------|
| Display name | GraphRAG Knowledge Base |
| Internal name | `LiamGraphRAGKB` |
| Source | `components/liam/kb_instance.py` |
| Role | Create or connect a KB instance used by index / retrieve / maintain / provenance |

## Purpose

Pick a storage backend (AstraDB / ArangoDB), configure connection and collection prefix, and emit a KB instance other GraphRAG components consume.

The UI is **backend-aware**: changing **Storage backend** shows only that backend’s connection fields (Astra vs Arango). Under Astra, **Data API environment** `hcd` reveals username/password; `astra` uses Token instead.

## Main inputs

| Parameter | Notes |
|-----------|-------|
| Storage backend | `AstraDB` or `ArangoDB` — switches visible fields immediately |
| Knowledge base name | UI display name |
| Collection prefix | Storage prefix; derives `_chunks` / `_entities` / … **Do not** append `_chunks` yourself |
| Create if missing | Auto-create target collections when absent |
| Astra / Data API *(Astra only)* | Endpoint, Token (cloud), Keyspace; environment `astra` / `hcd` |
| Data API username/password *(Astra + hcd only)* | Advanced; local/self-hosted Data API |
| Arango *(Arango only)* | URL, username, password, database, graph name, vector index factory |
| Enable vector ANN retrieval | Default on; approximate search via backend indexes |
| Fall back to exact cosine if ANN fails | Recommended on |
| Vector similarity | Default `cosine` (shared) |

## Outputs

| Output | Notes |
|--------|-------|
| KB instance | `Data` for Index Builder / Retrieve / Maintain / Provenance |

## Typical wiring

```text
[GraphRAG Knowledge Base] → KB instance → [GraphRAG Index Builder]
                                         → [GraphRAG Retrieve]
                                         → [GraphRAG Maintain]
                                         → [GraphRAG Provenance]
```

## Notes

- Retrieve must use the **same prefix and database** as indexing.  
- Arango needs vector-index capability; see [../guides/arango.md](../guides/arango.md).  
- After changing Embedding models, rebuild to avoid dimension mismatches.

## Related

- [Index Builder](graphrag-build.md)  
- [Retrieve](graphrag-retrieve.md)  
- [Quickstart](../guides/quickstart.md)

# Minimal working flow

First-time path to get GraphRAG running end to end.

## Prerequisites

| Backend | You need |
|---------|----------|
| AstraDB | Endpoint, Token, collection prefix; Embedding + LLM |
| ArangoDB | URL, database, credentials, prefix; vector index enabled; Embedding + LLM |

## Steps

1. **GraphRAG Knowledge Base**  
   - Pick a backend; prefix e.g. `liam_graphrag`  
   - Keep **Enable vector ANN retrieval** on  
   - Run until status shows connected  

2. **GraphRAG Index Builder**  
   - Wire KB instance, documents, Embedding, LLM  
   - Indexing method: **Standard GraphRAG** or **FastGraphRAG**  
   - Write mode: **Rebuild index** for the first successful run  
   - Confirm summary has entities/communities/reports and ANN ready  

3. **GraphRAG Retrieve**  
   - Same KB + **same Embedding** as indexing  
   - Start with Local Search on a concrete question  

Optional:

- **GraphRAG Provenance**: verify sources by entity name or text-unit ID  
- **GraphRAG Maintain**: view **Stats**; to clear, type exactly `CONFIRM DELETE`

## Wiring sketch

```text
[Documents] ──┐
[Embedding] ──┤
[LLM] ────────┼→ [Index Builder] → [Retrieve] → answer
[KB] ─────────┘
```

## Related

- [Knowledge Base](../components/graphrag-kb.md)  
- [Index Builder](../components/graphrag-build.md)  
- [Retrieve](../components/graphrag-retrieve.md)  
- [Arango troubleshooting](arango.md)

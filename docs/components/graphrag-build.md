# GraphRAG Index Builder

| Item | Value |
|------|-------|
| Display name | GraphRAG Index Builder |
| Internal name | `LiamGraphRAGBuild` |
| Source | `components/liam/kb_build.py` |
| Role | Index documents: chunk → extract → communities → reports → vectors / ANN |

## Purpose

Run the full indexing pipeline on a **GraphRAG Knowledge Base** instance. Two methods:

- **Standard GraphRAG**: LLM entities/relationships + gleaning (higher quality, costlier)  
- **FastGraphRAG**: NLP noun phrases + co-occurrence (faster/cheaper, noisier; fine for Global-style summaries)

Then Leiden communities → community reports → embeddings and ANN indexes.

## Main inputs

| Parameter | Notes |
|-----------|-------|
| KB instance | Output of GraphRAG Knowledge Base |
| Documents to index | `Data` / `DataFrame` / `Table` list |
| Embedding model | Required for TextUnit / entity / report vectors |
| Language model (LLM) | Required; Standard extract + reports; Fast still needs reports |
| Indexing method | Standard GraphRAG / FastGraphRAG |
| Enable built-in token chunking | Default on; off → each item is one TextUnit |
| Chunk size / overlap | Defaults ~1200 / 100 tokens |
| Gleaning rounds | Standard only; `1` is a good start |
| Extract claims | Default off; Standard only |
| Max community size / levels | Leiden advanced knobs |
| Entity types | Comma-separated types for Standard extract |
| Write mode | Rebuild index / Append merge |

## Outputs

| Output | Notes |
|--------|-------|
| KB instance | Same instance after indexing (wire to Retrieve) |
| Build summary | Counts, ANN state, etc. |

## Typical wiring

```text
[Documents] ──┐
[Embedding] ──┤
[LLM] ────────┼→ [GraphRAG Index Builder] → [GraphRAG Retrieve]
[KB] ─────────┘
```

## Notes

- After enabling or fixing Arango vectors, prefer **Rebuild index** once.  
- Summary should show entity/community/report counts and vector ANN ready.  
- FastGraphRAG may extract nothing from tiny / phrase-poor text—use longer text or Standard.

## Related

- [Knowledge Base](graphrag-kb.md)  
- [Retrieve](graphrag-retrieve.md)  
- [Quickstart](../guides/quickstart.md)

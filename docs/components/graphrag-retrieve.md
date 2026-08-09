# GraphRAG Retrieve

| Item | Value |
|------|-------|
| Display name | GraphRAG Retrieve |
| Internal name | `LiamGraphRAGRetrieve` |
| Source | `components/liam/kb_retrieve.py` |
| Role | Local / Global / DRIFT search over an indexed KB |

## Purpose

Three modes:

| Mode | Best for | Needs |
|------|----------|-------|
| Local Search | Concrete facts / entity questions | Embedding; LLM if generating answers |
| Global Search | Theme-level summaries across communities | LLM |
| DRIFT Search | Community primer + Local follow-ups | Embedding + LLM |

## Main inputs

| Parameter | Notes |
|-----------|-------|
| KB instance | Indexed instance |
| Embedding model | Required for Local / DRIFT; must match indexing |
| Language model (LLM) | Required for Global / DRIFT; Local for answers |
| Query | User question |
| Search mode | Local Search / Global Search / DRIFT Search |
| Conversation history | Optional multi-turn context |
| Response style | e.g. Multi-paragraph answer |
| Context token budget | Total packing budget |
| Local text-unit / community shares | Budget split (percent) |
| Global dynamic selection / general knowledge / map concurrency / level | Global advanced |
| DRIFT follow-up rounds / primer reports / max follow-ups | DRIFT advanced |
| Local entity / text-unit counts | Local recall size |
| Local answer with LLM | Off → mostly return context |

## Outputs

| Output | Notes |
|--------|-------|
| Results | Structured hits (documents / reports) |
| Answer / context | Natural-language answer or packed context |

## Typical wiring

```text
[KB] ────────┐
[Embedding] ─┼→ [GraphRAG Retrieve] → answer
[LLM] ───────┘
```

## Notes

- Embedding mismatch vs indexing hurts quality or causes dimension errors.  
- Healthy Local meta often includes `vector_ranking=ann:*` and `index_load=subgraph`.  
- DRIFT uses more LLM calls than Local—watch rate limits and cost.

## Related

- [Index Builder](graphrag-build.md)  
- [Provenance](graphrag-provenance.md)  
- [Quickstart](../guides/quickstart.md)

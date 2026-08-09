# GraphRAG Provenance

| Item | Value |
|------|-------|
| Display name | GraphRAG Provenance |
| Internal name | `LiamGraphRAGProvenance` |
| Source | `components/liam/kb_provenance.py` |
| Role | Bidirectional entity ↔ text unit ↔ document provenance |

## Purpose

Indexing writes bidirectional links. Use this control to verify answers are grounded:

| Lookup direction | Meaning |
|------------------|---------|
| Entity → Text Units | Which TextUnits support an entity |
| Text Unit → Entities | Entities/relationships from a unit |
| Document → Graph Elements | Graph elements aggregated by document |

## Main inputs

| Parameter | Notes |
|-----------|-------|
| KB instance | Indexed instance |
| Lookup direction | One of the three above |
| Lookup key | Entity name/ID, text-unit ID, or document ID/title |

## Outputs

| Output | Notes |
|--------|-------|
| Provenance result | Structured provenance payload |
| KB instance | Pass-through for chaining |

## Typical wiring

```text
[GraphRAG Knowledge Base] → [GraphRAG Provenance] → provenance result
```

You can also look up entity names or TextUnit IDs from a retrieve answer.

## Notes

- Index first; otherwise there are no links to query.  
- Match key type to lookup direction.  
- Citations from Local / DRIFT can be cross-checked here.

## Related

- [Retrieve](graphrag-retrieve.md)  
- [Index Builder](graphrag-build.md)

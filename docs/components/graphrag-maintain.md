# GraphRAG Maintain

| Item | Value |
|------|-------|
| Display name | GraphRAG Maintain |
| Internal name | `LiamGraphRAGMaintain` |
| Source | `components/liam/kb_maintain.py` |
| Role | Show knowledge-model stats, or clear the KB (destructive) |

## Purpose

- **Stats**: text units, entities, relationships, communities, reports, claims.  
- **Clear knowledge base**: delete GraphRAG data under the prefix (irreversible).

## Main inputs

| Parameter | Notes |
|-----------|-------|
| KB instance | Target instance |
| Operation | `Stats` / `Clear knowledge base` |
| Clear confirmation phrase | For clear, type exactly: `CONFIRM DELETE` |

## Outputs

| Output | Notes |
|--------|-------|
| KB instance | Instance after the operation |
| Operation result | Stats or clear result message |

## Typical wiring

```text
[GraphRAG Knowledge Base] → [GraphRAG Maintain] → operation result
```

## Notes

- Clear is destructive; the confirmation phrase must match exactly: `CONFIRM DELETE`.  
- After clear, run Index Builder again before retrieve.  
- Double-check the prefix so you do not wipe another dataset.

## Related

- [Knowledge Base](graphrag-kb.md)  
- [Index Builder](graphrag-build.md)

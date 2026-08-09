# Toolkit overview

## Positioning

`lfx-liam-bundle` is a personal **Langflow Extension toolkit**, not a single-feature product.  
It currently ships GraphRAG components; further capabilities should join the same `liam` bundle.

## Architecture

```text
langflow.extensions entry-point
  └─ lfx_liam_bundle / extension.json
       ├─ components/liam/*      # Langflow UI components
       └─ domain packages (e.g. graphrag/*)
```

| Layer | Path | Role |
|-------|------|------|
| Extension manifest | `extension.json` | Extension id, display name, bundle registration |
| Components | `src/lfx_liam_bundle/components/liam/` | Parameters, validation, English UI copy, wiring |
| Domain | `src/lfx_liam_bundle/graphrag/` etc. | Reusable logic decoupled from UI |

## Adding a component

1. Add and export a component class under `components/liam/`.  
2. Write a page under `docs/components/` and update [index.md](index.md).  
3. Keep complex logic in a domain package; do not force every feature into GraphRAG.

## Related

- Component list: [index.md](index.md)  
- Install: [guides/install.md](guides/install.md)  
- Quickstart: [guides/quickstart.md](guides/quickstart.md)

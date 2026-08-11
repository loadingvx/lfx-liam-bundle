# lfx-liam-bundle docs

This repository is **Liam’s Langflow extension toolkit** (bundle: `liam`).  
Docs are organized as toolkit overview → component pages → shared guides. Add one page under `components/` for each new Langflow control.

## Layout

```text
docs/
  index.md                 # This page
  overview.md              # Toolkit architecture
  components/              # One page per Langflow component
  guides/                  # Install, quickstart, ops
```

## Components (current)

| Display name | Internal name | Docs |
|--------------|---------------|------|
| GraphRAG Knowledge Base | `LiamGraphRAGKB` | [components/graphrag-kb.md](components/graphrag-kb.md) |
| GraphRAG Index Builder | `LiamGraphRAGBuild` | [components/graphrag-build.md](components/graphrag-build.md) |
| GraphRAG Retrieve | `LiamGraphRAGRetrieve` | [components/graphrag-retrieve.md](components/graphrag-retrieve.md) |
| GraphRAG Maintain | `LiamGraphRAGMaintain` | [components/graphrag-maintain.md](components/graphrag-maintain.md) |
| GraphRAG Provenance | `LiamGraphRAGProvenance` | [components/graphrag-provenance.md](components/graphrag-provenance.md) |

## Guides

| Doc | Content |
|-----|---------|
| [overview.md](overview.md) | Layering and how to extend |
| [guides/install.md](guides/install.md) | Install into Langflow |
| [guides/graphrag-usage.md](guides/graphrag-usage.md) | GraphRAG wiring: who connects to whom |
| [guides/quickstart.md](guides/quickstart.md) | Minimal working flow |
| [guides/arango.md](guides/arango.md) | ArangoDB setup and troubleshooting |

## Maintenance

1. **New Langflow component**: add a page under `docs/components/` and a row in the table above.  
2. **Component page structure**: purpose → inputs/outputs → wiring → notes → related docs.  
3. **Cross-cutting topics** (install, DB ops) go in `guides/`, not copied into every component page.  
4. Root [README.md](../README.md) / [README.zh-CN.md](../README.zh-CN.md) stay high-level; details live here.

UI labels, help text, and status messages for these components are in **English**.

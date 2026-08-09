# Install

## PyPI

```bash
pip install lfx-liam-bundle
```

Requires Python **3.10+**. Langflow discovers this package via the `langflow.extensions` entry-point.

## Local Docker Langflow (optional)

```bash
./scripts/deploy-to-docker.sh
```

Hard-refresh the browser, then open the **Liam** group in the component panel, or search `GraphRAG` / `Liam`.

## Development install

```bash
mise exec -- uv sync
# or
pip install -e .
```

Editable resolution defaults to sibling `../langflow/src/lfx` (see `pyproject.toml`).

## Verify

```bash
mise exec -- uv run pytest -m "not integration"
```

Optional real-DB integration:

```bash
./devops/db-up.sh && ./devops/test-integration.sh
```

## Related

- [Quickstart](quickstart.md)  
- [Docs home](../index.md)

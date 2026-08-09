# 安装与接入

## PyPI 安装

```bash
pip install lfx-liam-bundle
```

需要 Python **3.10+**。Langflow 通过 `langflow.extensions` 入口自动发现本扩展。

## 装入本地 Docker Langflow（可选）

```bash
./scripts/deploy-to-docker.sh
```

安装后硬刷新浏览器，在组件面板打开 **Liam** 分组，或搜索 `GraphRAG` / `Liam`。

## 开发安装

```bash
./scripts/setup-env.sh
# 或
mise exec -- uv sync
```

依赖解析默认 editable 指向旁边的 `../langflow/src/lfx`（见 `pyproject.toml`）。

## 验证

```bash
mise exec -- uv run pytest -m "not integration"
```

真库集成（可选）：

```bash
./devops/db-up.sh
./devops/test-integration.sh
```

## 相关文档

- [最短 Flow](quickstart.md)  
- [文档首页](../index.md)

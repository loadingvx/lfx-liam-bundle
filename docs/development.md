# 开发指南

## 环境

本仓库用 **mise + uv** 管理工具链（见 `mise.toml`）。

```bash
./scripts/setup-env.sh
# 等价
make setup
```

依赖解析时，`lfx` 默认 editable 指向 `../langflow/src/lfx`。
若你只有独立克隆、没有旁边的 langflow 源码：

1. 临时注释/调整 `pyproject.toml` 里 `[tool.uv.sources]`
2. 或 `uv add "lfx>=1.11,<2"` 走 PyPI / 现网版本

## 日常循环

```bash
# 改代码后
make validate   # manifest + 静态检查
make test       # 单测
make lint       # ruff

# 或一次跑完
make check
```

装入本地 docker Langflow：

```bash
make deploy-docker
```

官方 Mode A（本机起 Langflow 并热加载本扩展）：

```bash
mise exec -- uv run lfx extension dev .
```

## 加新组件

1. 在 `src/lfx_liam_bundle/components/liam/` 新增 `*.py`，继承 `lfx` 的 `Component`
2. 在 `components/liam/__init__.py` 与包根 `__init__.py` 导出
3. 领域逻辑放 `graphrag/`，组件内只做接线与错误文案
4. 补 `tests/`，保证无外部 DB 也能跑的纯逻辑覆盖
5. `make check` 通过后再提 PR

## 版本 bump 清单

发布前同步这些位置：

- `pyproject.toml` → `project.version`
- 根目录 `extension.json` → `version`
- `src/lfx_liam_bundle/extension.json` → `version`
- `src/lfx_liam_bundle/__init__.py` → `__version__`
- `CHANGELOG.md`

## 发布期望（PyPI）

GitHub Actions（`.github/workflows/python-publish.yml`）在 **Release published** 时执行：

1. 校验 tag 与下列版本一致（去掉前缀 `v`）：
   - `pyproject.toml` → `project.version`
   - `src/lfx_liam_bundle/__init__.py` → `__version__`
   - 根目录与包内两份 `extension.json` → `version`
2. `python -m build` 产出 sdist / wheel
3. 通过 Trusted Publishing（OIDC + Environment `pypi`）上传到 PyPI：`lfx-liam-bundle`

本地门禁仍用：`make check`（validate + lint + test），再 `make build`。

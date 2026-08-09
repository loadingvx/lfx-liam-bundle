# 开发指南

## 环境

本仓库用 **mise + uv** 管理工具链（见 `mise.toml`）。

- **最低 / 本地开发 Python：3.10**（与 `lfx`、`requires-python = ">=3.10,<3.15"` 对齐）
- 有 3.10 即可开发、测试、发版；更高版本（3.11–3.14）亦可运行，但本机默认钉在 3.10

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

## 版本 bump（尽量少改）

手写版本号只保留 **3 处**（其余勿写死具体号）：

| 文件 | 字段 | 说明 |
|------|------|------|
| `pyproject.toml` | `project.version` | 权威源 |
| `extension.json` | `version` | Mode A / `lfx extension validate` |
| `src/lfx_liam_bundle/extension.json` | `version` | 打进 wheel，运行时发现 |

推荐一键同步：

```bash
./scripts/bump-version.sh 0.0.2   # 改三处并校验
# 再把 CHANGELOG.md 的 [Unreleased] 固化为对应版本
```

`__version__` 由 `importlib.metadata` 读取包装版本，**不要**在 `__init__.py` 手写字面量。  
文档示例用 `X.Y.Z` / `pip show`，不要钉死某一版。

本地校验：`make check-versions`（已纳入 `make check`）。  
发版 CI 会再跑 `./scripts/check-versions.sh <tag>`。

## 发布期望（PyPI）

GitHub Actions（`.github/workflows/python-publish.yml`）在 **Release published** 时执行：

1. `./scripts/check-versions.sh <tag>`：tag（可带/不带 `v`）与上述三处一致
2. 校验 `requires-python` 允许 3.10，并用 **Python 3.10** 执行 `python -m build`
3. 通过 Trusted Publishing（OIDC + Environment `pypi`）上传到 PyPI：`lfx-liam-bundle`

本地门禁：`make check`（check-versions + validate + lint + test），再 `make build`。

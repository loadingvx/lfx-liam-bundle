# 贡献指南

感谢你为 **lfx-liam-bundle** 做贡献。本仓库是符合 Langflow Extension 规范的
独立 bundle，贡献前请先读完本文。

## 行为准则

参与本项目即表示你同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 开发环境

### 前置条件

- [mise](https://mise.jdx.dev/)（管理 Python / uv）
- 目录布局建议：

```text
arch_workspace/langflow/
├── langflow/            # 官方 Langflow（含 src/lfx）
└── lfx-liam-bundle/     # 本仓库
```

本仓库 `pyproject.toml` 通过 `tool.uv.sources` 将 `lfx` 指向
`../langflow/src/lfx`，以便与本地 docker 开发环境版本对齐。

### 一键初始化

```bash
./scripts/setup-env.sh
```

或手动：

```bash
mise install
mise exec -- uv sync --group dev
mise exec -- uv run lfx extension validate .
mise exec -- uv run pytest
```

也可用 Makefile：

```bash
make setup
make check
```

### 装入已运行的 Langflow Docker

若你已用官方 compose 跑着 Langflow：

```bash
./scripts/deploy-to-docker.sh
```

然后打开 http://localhost:5173 ，在 Components 中搜索 `GraphRAG`。

## 目录约定（必须遵守）

```text
lfx-liam-bundle/
├── extension.json                 # 根清单（validate / Mode A 开发用）
├── pyproject.toml                 # pip 可安装包 + entry-point
├── src/lfx_liam_bundle/
│   ├── extension.json             # 打进 wheel，供运行时发现
│   ├── components/liam/           # UI 组件（bundles[].path）
│   └── graphrag/                  # 纯逻辑（无 lfx UI 依赖更佳）
└── tests/
```

关键约束（来自 [Langflow Extensions 文档](https://docs.langflow.org/extensions-quickstart)）：

1. `extension.json` 的 `bundles[].path`：
   - 根清单相对仓库根：`src/lfx_liam_bundle/components/liam`
   - 包内清单相对包目录：`components/liam`
2. 组件只依赖公开 `lfx.*` BUNDLE_API，不要 `from langflow...`
3. 版本号同步：`pyproject.toml`、根/`src` 两份 `extension.json`、`__version__`
4. 用户可见文案优先中文，错误信息要可操作

## 提交流程

1. Fork / 建分支：`feat/...`、`fix/...`、`docs/...`
2. 改代码 + 补测试
3. 本地门禁：

```bash
make check
```

4. 更新 `CHANGELOG.md` 的 `[Unreleased]`
5. 开 PR，按模板勾选测试项

## 提交信息

建议 Conventional Commits：

```text
feat: 支持 Arango 社区检索超时提示
fix: Astra token 为空时给出中文错误
docs: 补充安装到生产环境步骤
test: 覆盖 edge_definition 解析边界
```

## 发布（维护者）

```bash
# 1.  bump 版本（三处 extension / pyproject / __init__）
# 2. CHANGELOG 固化版本日期
# 3. 构建
make build
# 4. 打 tag：vX.Y.Z 并推送
# 5. 按需 twine upload dist/*
```

## 需要帮助？

- 使用问题：开 Issue（Bug / 功能）
- 安全问题：见 [SECURITY.md](SECURITY.md)

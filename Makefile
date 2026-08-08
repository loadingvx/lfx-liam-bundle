# lfx-liam-bundle 常用开发命令
# 用法: make <target>

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
export MISE_TRUSTED_CONFIG_PATHS := $(if $(MISE_TRUSTED_CONFIG_PATHS),$(MISE_TRUSTED_CONFIG_PATHS):)$(ROOT)/mise.toml

.PHONY: help setup sync validate test lint format check build deploy-docker clean

help: ## 显示可用命令
	@awk 'BEGIN {FS = ":.*##"; printf "\nTargets:\n" } \
		/^[a-zA-Z_-]+:.*?##/ { printf "  %-16s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

define RUN_UV
	if command -v mise >/dev/null 2>&1; then \
		mise exec -- uv $(1); \
	elif command -v uv >/dev/null 2>&1; then \
		uv $(1); \
	else \
		echo "错误: 未找到 mise/uv，请先安装 mise: https://mise.jdx.dev/" >&2; \
		exit 1; \
	fi
endef

setup: ## 初始化本地开发环境
	@$(ROOT)/scripts/setup-env.sh

sync: ## 同步依赖（含 dev）
	@$(call RUN_UV,sync --group dev)

validate: ## 校验 extension manifest
	@$(call RUN_UV,run lfx extension validate .)

test: ## 运行单元测试
	@$(call RUN_UV,run pytest)

lint: ## ruff 静态检查
	@$(call RUN_UV,run ruff check src tests)
	@$(call RUN_UV,run ruff format --check src tests)

format: ## ruff 自动格式化
	@$(call RUN_UV,run ruff check --fix src tests)
	@$(call RUN_UV,run ruff format src tests)

check: validate lint test ## 发布前本地门禁

build: ## 构建 sdist + wheel 到 dist/
	@rm -rf $(ROOT)/dist
	@$(call RUN_UV,run python -m build)
	@ls -la $(ROOT)/dist

deploy-docker: ## 安装进本地 Langflow docker compose
	@$(ROOT)/scripts/deploy-to-docker.sh

clean: ## 清理构建与缓存
	@rm -rf $(ROOT)/dist $(ROOT)/build $(ROOT)/.pytest_cache $(ROOT)/.ruff_cache $(ROOT)/htmlcov $(ROOT)/.coverage
	@find $(ROOT)/src $(ROOT)/tests -type d -name '__pycache__' -prune -exec rm -rf {} +

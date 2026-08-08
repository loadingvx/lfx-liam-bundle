#!/usr/bin/env bash
# 初始化 Liam Bundle 本地开发环境（mise + uv）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v mise >/dev/null 2>&1; then
  echo "错误: 未找到 mise。请先安装 mise: https://mise.jdx.dev/"
  exit 1
fi

if [[ ! -d ../langflow/src/lfx ]]; then
  echo "错误: 找不到 ../langflow/src/lfx"
  echo "请保持目录布局: arch_workspace/langflow/{langflow,lfx-liam-bundle}"
  exit 1
fi

# 避免交互式 trust 打断脚本；同时兼容沙箱/权限受限环境
export MISE_TRUSTED_CONFIG_PATHS="${MISE_TRUSTED_CONFIG_PATHS:+$MISE_TRUSTED_CONFIG_PATHS:}$ROOT/mise.toml"
mise trust --yes "$ROOT/mise.toml" 2>/dev/null || true

run_uv() {
  if mise exec -- uv "$@" 2>/dev/null; then
    return 0
  fi
  # fallback：系统已有 uv，且本目录已有/可创建 .venv
  if command -v uv >/dev/null 2>&1; then
    echo "提示: mise exec 不可用，回退到系统 uv"
    uv "$@"
    return $?
  fi
  echo "错误: 无法通过 mise 或系统 PATH 调用 uv"
  exit 1
}

echo ">>> mise install（python / uv，失败时回退系统工具）"
if ! mise install; then
  echo "提示: mise install 未完全成功，将尝试使用已有 python/uv 继续"
fi

echo ">>> uv sync（含 dev 依赖；lfx 指向 ../langflow/src/lfx）"
run_uv sync --group dev

echo
echo "环境就绪。"
echo "  一键门禁: make check"
echo "  校验:     mise exec -- uv run lfx extension validate ."
echo "  测试:     mise exec -- uv run pytest"
echo "  本地dev:  mise exec -- uv run lfx extension dev ."
echo "  装入docker: ./scripts/deploy-to-docker.sh  或  make deploy-docker"
echo "  贡献指南: CONTRIBUTING.md"

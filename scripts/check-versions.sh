#!/usr/bin/env bash
# 校验仓库内「需要手写」的版本号一致。
#
# 唯一手写来源（发版时改这三处，或用 scripts/bump-version.sh）：
#   1. pyproject.toml → [project].version          （权威源）
#   2. extension.json → version                   （Mode A / validate）
#   3. src/lfx_liam_bundle/extension.json → version（打进 wheel）
#
# __version__ 由 importlib.metadata 读取包装版本，不再手写。
# 文档勿写死具体版本号（示例用 X.Y.Z / pip show）。
#
# 用法:
#   ./scripts/check-versions.sh           # 三者互相同步
#   ./scripts/check-versions.sh 0.0.1     # 再与期望版本（Release tag 去 v）比对
#   ./scripts/check-versions.sh v0.0.1

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

EXPECTED_RAW="${1:-}"
EXPECTED="${EXPECTED_RAW#v}"

read_pyproject_version() {
  sed -nE 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' pyproject.toml | head -n1
}

read_json_version() {
  local file="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['version'])" "${file}"
  else
    sed -nE 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "${file}" | head -n1
  fi
}

die() {
  echo "::error::$*" >&2
  echo "错误: $*" >&2
  exit 1
}

PROJECT_VERSION="$(read_pyproject_version)"
ROOT_EXT_VERSION="$(read_json_version extension.json)"
PKG_EXT_VERSION="$(read_json_version src/lfx_liam_bundle/extension.json)"

echo "pyproject.toml:                      ${PROJECT_VERSION:-<空>}"
echo "extension.json:                      ${ROOT_EXT_VERSION:-<空>}"
echo "src/lfx_liam_bundle/extension.json:  ${PKG_EXT_VERSION:-<空>}"

if [[ -z "${PROJECT_VERSION}" || -z "${ROOT_EXT_VERSION}" || -z "${PKG_EXT_VERSION}" ]]; then
  die "未能解析版本号。请确认 pyproject.toml 与两份 extension.json 均含 version 字段。"
fi

if [[ "${ROOT_EXT_VERSION}" != "${PROJECT_VERSION}" || "${PKG_EXT_VERSION}" != "${PROJECT_VERSION}" ]]; then
  die "版本不一致。权威源为 pyproject.toml=${PROJECT_VERSION}；请同步两份 extension.json，或执行: ./scripts/bump-version.sh ${PROJECT_VERSION}"
fi

# 防止有人又把发布用字面量写回 __init__.py（允许 "0.0.0+local" 兜底）
if grep -nE '^[[:space:]]*__version__[[:space:]]*=[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' \
  src/lfx_liam_bundle/__init__.py >/dev/null 2>&1; then
  die "src/lfx_liam_bundle/__init__.py 不应手写发布用 __version__ 字面量；请用 importlib.metadata.version(\"lfx-liam-bundle\")。"
fi

if [[ -n "${EXPECTED}" ]]; then
  echo "期望版本（tag）:                     ${EXPECTED}"
  if [[ "${PROJECT_VERSION}" != "${EXPECTED}" ]]; then
    die "版本与 Release tag 不一致：仓库为 ${PROJECT_VERSION}，tag 期望 ${EXPECTED}。请先 bump 再发版（tag 可用 v${EXPECTED}）。"
  fi
fi

echo "版本校验通过（手写三处均为 ${PROJECT_VERSION}）。"

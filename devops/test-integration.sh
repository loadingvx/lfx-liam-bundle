#!/usr/bin/env bash
# 对真实目标库跑集成测试（默认先确保 Arango compose 已起）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if [[ -f "${ROOT}/devops/.env.integration" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "${ROOT}/devops/.env.integration"
  set +a
fi

export LFX_LIAM_ARANGO_URL="${LFX_LIAM_ARANGO_URL:-http://127.0.0.1:18529}"
export LFX_LIAM_ARANGO_PASSWORD="${LFX_LIAM_ARANGO_PASSWORD:-liamtest}"
export LFX_LIAM_ARANGO_USERNAME="${LFX_LIAM_ARANGO_USERNAME:-root}"
export LFX_LIAM_ARANGO_DATABASE="${LFX_LIAM_ARANGO_DATABASE:-_system}"

SKIP_UP=0
PYTEST_ARGS=()
for arg in "$@"; do
  if [[ "${arg}" == "--skip-up" ]]; then
    SKIP_UP=1
  else
    PYTEST_ARGS+=("${arg}")
  fi
done

if [[ "${SKIP_UP}" -eq 0 ]]; then
  "${ROOT}/devops/db-up.sh"
fi

echo "→ 运行集成测试（pytest -m integration）…"
mise exec -- uv run pytest -m integration -v --tb=short "${PYTEST_ARGS[@]}"
echo "✅ 集成测试完成"

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${ROOT}/devops/docker-compose.yml"
cd "${ROOT}"

KEEP_DATA="${1:-}"
if [[ "${KEEP_DATA}" == "--keep-data" ]]; then
  docker compose -f "${COMPOSE_FILE}" down
  echo "✅ 已停止容器（保留 volume）"
else
  docker compose -f "${COMPOSE_FILE}" down -v
  echo "✅ 已停止容器并删除 volume"
fi

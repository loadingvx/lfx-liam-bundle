#!/usr/bin/env bash
# 启动本地目标库（ArangoDB + vector-index）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${ROOT}/devops/docker-compose.yml"
cd "${ROOT}"

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker 不可用。请先启动 Docker。"
  exit 1
fi

# 镜像兜底：官方 hub 超时则走 DaoCloud library 镜像
if ! docker image inspect arangodb:3.12.4 >/dev/null 2>&1; then
  echo "→ 拉取 arangodb:3.12.4 …"
  if ! docker pull arangodb:3.12.4; then
    echo "→ docker hub 失败，改用 docker.m.daocloud.io/library/arangodb:3.12.4"
    docker pull docker.m.daocloud.io/library/arangodb:3.12.4
    docker tag docker.m.daocloud.io/library/arangodb:3.12.4 arangodb:3.12.4
  fi
fi

echo "→ docker compose up -d arangodb"
docker compose -f "${COMPOSE_FILE}" up -d arangodb

PORT="${LFX_LIAM_ARANGO_PORT:-18529}"
PASS="${LFX_LIAM_ARANGO_PASSWORD:-liamtest}"
echo "→ 等待 Arango 健康（宿主机探测 :${PORT}）…"
for i in $(seq 1 60); do
  if VER="$(curl -sf -u "root:${PASS}" "http://127.0.0.1:${PORT}/_api/version" 2>/dev/null)"; then
    echo "✅ ArangoDB 就绪: ${VER}"
    echo "   URL: http://127.0.0.1:${PORT}"
    echo "   用户: root / 密码: ${PASS}"
    echo "   已开启 --experimental-vector-index（3.12.4）"
    exit 0
  fi
  sleep 2
done

echo "❌ ArangoDB 启动超时。请检查：docker compose -f devops/docker-compose.yml logs arangodb"
exit 1

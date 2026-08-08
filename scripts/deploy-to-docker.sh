#!/usr/bin/env bash
# 构建/同步 lfx-liam-bundle，并让 Langflow docker compose 开发环境加载它。
#
# 原理（重要）:
#   docker/dev.start.sh 每次启动都会 `uv sync --frozen`，会清掉临时 pip 安装。
#   因此本工程通过 compose 挂载到 /opt/extensions/lfx-liam-bundle，
#   并在 sync 之后以 editable 方式重新安装，才能在 Bundles 面板稳定出现。
#
# 用法:
#   ./scripts/deploy-to-docker.sh              # 校验 + 重建 langflow 服务 + 健康检查
#   ./scripts/deploy-to-docker.sh --validate-only
#   ./scripts/deploy-to-docker.sh --no-recreate # 仅容器内即时 pip 安装（下次重启仍靠 start.sh）
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LANGFLOW_ROOT="$(cd "$ROOT/../langflow" && pwd)"
COMPOSE_FILE="$LANGFLOW_ROOT/docker/dev.docker-compose.yml"
SERVICE="langflow"
CONTAINER_NAME="dev-langflow"
EXT_MOUNT="/opt/extensions/lfx-liam-bundle"

export MISE_TRUSTED_CONFIG_PATHS="${MISE_TRUSTED_CONFIG_PATHS:+$MISE_TRUSTED_CONFIG_PATHS:}$ROOT/mise.toml"

NO_RECREATE=0
VALIDATE_ONLY=0

die() { echo "错误: $*" >&2; exit 1; }
info() { echo ">>> $*"; }

run_uv() {
  if command -v mise >/dev/null 2>&1; then
    if mise exec -- uv "$@" ; then
      return 0
    fi
  fi
  if command -v uv >/dev/null 2>&1; then
    uv "$@"
    return $?
  fi
  die "无法调用 uv（mise/系统均不可用）"
}

for arg in "$@"; do
  case "$arg" in
    --no-recreate) NO_RECREATE=1 ;;
    --validate-only) VALIDATE_ONLY=1 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg"
      echo "支持: --no-recreate | --validate-only | --help"
      exit 1
      ;;
  esac
done

command -v docker >/dev/null 2>&1 || die "未找到 docker"
[[ -f "$COMPOSE_FILE" ]] || die "找不到 compose 文件: $COMPOSE_FILE"

COMPOSE=(docker compose -f "$COMPOSE_FILE")

wait_health() {
  local i
  info "等待后端健康检查 http://127.0.0.1:7860/health ..."
  for i in $(seq 1 60); do
    if curl -sf -m 2 http://127.0.0.1:7860/health >/dev/null 2>&1; then
      echo "后端已就绪"
      return 0
    fi
    sleep 5
  done
  die "后端未在预期时间内就绪。请查看: cd $LANGFLOW_ROOT && docker compose -f docker/dev.docker-compose.yml logs -f langflow"
}

install_in_container() {
  info "在容器内 editable 安装（--no-deps）"
  "${COMPOSE[@]}" exec -T "$SERVICE" sh -c "
    set -e
    if [[ ! -f ${EXT_MOUNT}/pyproject.toml ]]; then
      echo '错误: 容器内未挂载 ${EXT_MOUNT}。请确认 docker/dev.docker-compose.yml 已包含该 volume，并执行 compose up -d。' >&2
      exit 1
    fi
    if [[ ! -x /app/.venv/bin/python ]]; then
      echo '错误: /app/.venv/bin/python 不可用' >&2
      exit 1
    fi
    uv pip install --python /app/.venv/bin/python --force-reinstall --no-deps -e ${EXT_MOUNT}
    /app/.venv/bin/python -c \"import lfx_liam_bundle; print('import ok:', lfx_liam_bundle.__file__)\"
  "
}

verify_extension() {
  info "确认 extension 已注册"
  local out
  out="$("${COMPOSE[@]}" exec -T "$SERVICE" sh -c 'uv run lfx extension list' 2>&1)" || true
  if echo "$out" | grep -q 'lfx-liam-bundle'; then
    echo "extension list 已包含 lfx-liam-bundle"
    echo "$out" | grep -E 'lfx-liam-bundle|ID ' || true
  else
    echo "警告: extension list 未看到 lfx-liam-bundle。原始输出："
    echo "$out" | head -n 40
    die "扩展未加载。请查看容器启动日志中 [dev] installing local extension 段。"
  fi
}

cd "$ROOT"

if [[ ! -d .venv ]]; then
  info "本地 .venv 不存在，先初始化"
  "$ROOT/scripts/setup-env.sh"
fi

info "校验 extension manifest"
run_uv run lfx extension validate . || die "extension validate 失败"

if [[ "$VALIDATE_ONLY" -eq 1 ]]; then
  echo "仅校验完成（--validate-only）"
  exit 0
fi

if ! docker ps --filter "name=^${CONTAINER_NAME}$" --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  die "Langflow 容器未运行。请先: cd $LANGFLOW_ROOT && ./devops/dev-up.sh"
fi

if [[ "$NO_RECREATE" -eq 1 ]]; then
  # 需要 volume 已挂载；若尚未挂载会失败并提示 recreate
  install_in_container
  info "热安装完成。若 UI 仍无组件，请去掉 --no-recreate 重建服务，或刷新页面。"
  echo "注意: 完整重启仍依赖 start.sh 在 uv sync 后自动安装。"
else
  info "重建 langflow 服务（应用 volume 挂载 + start.sh 自动安装）"
  # up -d 会按最新 compose 重新创建容器；比 restart 更能挂上新 volume
  (cd "$LANGFLOW_ROOT" && "${COMPOSE[@]}" up -d --force-recreate "$SERVICE")
  wait_health
  # 双保险：若 start.sh 安装失败，这里再装一次
  install_in_container
fi

verify_extension

echo
echo "部署完成。"
echo "  UI:        http://localhost:5173"
echo "  查找位置:  Components → 搜索 GraphRAG / Liam"
echo "  组件:      GraphRAG 知识库 / 入库建图 / 检索 / 知识库维护"
echo "  校验:      docker compose exec langflow uv run lfx extension list"
echo "  若看不到:  硬刷新浏览器（Ctrl+Shift+R），并确认本脚本未报错"

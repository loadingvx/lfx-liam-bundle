#!/usr/bin/env bash
# 将手写版本号同步为同一值（权威源写入 pyproject + 两份 extension.json）。
#
# 用法:
#   ./scripts/bump-version.sh 0.0.2
#   ./scripts/bump-version.sh v0.0.2

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

RAW="${1:-}"
if [[ -z "${RAW}" ]]; then
  echo "用法: $0 <X.Y.Z>" >&2
  exit 2
fi

VERSION="${RAW#v}"
if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9._+-]*)?$ ]]; then
  echo "错误: 版本号格式无效: ${VERSION}（期望如 0.0.1 或 0.1.0rc1）" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 需要 python3 以安全改写 JSON。" >&2
  exit 1
fi

# pyproject.toml：只改 [project] 下第一处 version =
if grep -qE '^version[[:space:]]*=[[:space:]]*"' pyproject.toml; then
  sed -i -E '0,/^version[[:space:]]*=[[:space:]]*"[^"]*"/s//version = "'"${VERSION}"'"/' pyproject.toml
else
  echo "错误: pyproject.toml 中未找到 version = \"...\" 行。" >&2
  exit 1
fi

python3 - "${VERSION}" <<'PY'
import json
import sys
from pathlib import Path

version = sys.argv[1]
files = [
    Path("extension.json"),
    Path("src/lfx_liam_bundle/extension.json"),
]
for path in files:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {path}")
PY

echo "已 bump 至 ${VERSION}。正在校验…"
"${ROOT}/scripts/check-versions.sh" "${VERSION}"
echo
echo "提醒: 请同步更新 CHANGELOG.md（将 [Unreleased] 固化为 [${VERSION}]），再打 tag v${VERSION}。"

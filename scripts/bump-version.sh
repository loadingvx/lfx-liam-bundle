#!/usr/bin/env bash
# Sync handwritten versions to one value (pyproject + both extension.json files).
#
# Usage:
#   ./scripts/bump-version.sh 0.0.3
#   ./scripts/bump-version.sh v0.0.3

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

RAW="${1:-}"
if [[ -z "${RAW}" ]]; then
  echo "Usage: $0 <X.Y.Z>" >&2
  exit 2
fi

VERSION="${RAW#v}"
if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9._+-]*)?$ ]]; then
  echo "Error: invalid version: ${VERSION} (expected e.g. 0.0.3 or 0.1.0rc1)" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required to rewrite JSON safely." >&2
  exit 1
fi

# pyproject.toml: only the first version = under [project]
if grep -qE '^version[[:space:]]*=[[:space:]]*"' pyproject.toml; then
  sed -i -E '0,/^version[[:space:]]*=[[:space:]]*"[^"]*"/s//version = "'"${VERSION}"'"/' pyproject.toml
else
  echo "Error: version = \"...\" not found in pyproject.toml." >&2
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
    print(f"Updated {path}")
PY

echo "Bumped to ${VERSION}. Verifying…"
"${ROOT}/scripts/check-versions.sh" "${VERSION}"
echo
echo "Reminder: update CHANGELOG.md (move [Unreleased] to [${VERSION}]), then tag v${VERSION}."

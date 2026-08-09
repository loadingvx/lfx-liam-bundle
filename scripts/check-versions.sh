#!/usr/bin/env bash
# Verify handwritten versions stay in sync.
#
# Handwritten sources for release (edit these three, or use scripts/bump-version.sh):
#   1. pyproject.toml → [project].version           (source of truth)
#   2. extension.json → version                     (Mode A / validate)
#   3. src/lfx_liam_bundle/extension.json → version (packaged in the wheel)
#
# __version__ is read via importlib.metadata; do not hardcode a release version.
# Docs should not pin a concrete version (use X.Y.Z / pip show in examples).
#
# Usage:
#   ./scripts/check-versions.sh           # three-way sync check
#   ./scripts/check-versions.sh 0.0.3     # also compare to expected tag (strip leading v)
#   ./scripts/check-versions.sh v0.0.3

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
  echo "Error: $*" >&2
  exit 1
}

PROJECT_VERSION="$(read_pyproject_version)"
ROOT_EXT_VERSION="$(read_json_version extension.json)"
PKG_EXT_VERSION="$(read_json_version src/lfx_liam_bundle/extension.json)"

echo "pyproject.toml:                      ${PROJECT_VERSION:-<empty>}"
echo "extension.json:                      ${ROOT_EXT_VERSION:-<empty>}"
echo "src/lfx_liam_bundle/extension.json:  ${PKG_EXT_VERSION:-<empty>}"

if [[ -z "${PROJECT_VERSION}" || -z "${ROOT_EXT_VERSION}" || -z "${PKG_EXT_VERSION}" ]]; then
  die "Could not parse versions. Ensure pyproject.toml and both extension.json files define version."
fi

if [[ "${ROOT_EXT_VERSION}" != "${PROJECT_VERSION}" || "${PKG_EXT_VERSION}" != "${PROJECT_VERSION}" ]]; then
  die "Version mismatch. Source of truth is pyproject.toml=${PROJECT_VERSION}; sync both extension.json files, or run: ./scripts/bump-version.sh ${PROJECT_VERSION}"
fi

# Reject hardcoded release __version__ literals (allow "0.0.0+local" fallback)
if grep -nE '^[[:space:]]*__version__[[:space:]]*=[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' \
  src/lfx_liam_bundle/__init__.py >/dev/null 2>&1; then
  die "src/lfx_liam_bundle/__init__.py must not hardcode a release __version__; use importlib.metadata.version(\"lfx-liam-bundle\")."
fi

if [[ -n "${EXPECTED}" ]]; then
  echo "Expected (tag):                      ${EXPECTED}"
  if [[ "${PROJECT_VERSION}" != "${EXPECTED}" ]]; then
    die "Version does not match Release tag: repo=${PROJECT_VERSION}, tag expects ${EXPECTED}. Bump first, then publish (tag may be v${EXPECTED})."
  fi
fi

echo "Version check passed (all three handwritten sources are ${PROJECT_VERSION})."

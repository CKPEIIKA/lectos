#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

command -v uv >/dev/null 2>&1 || { echo "ERROR: uv is required" >&2; exit 127; }

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lectos-release.XXXXXX")"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

echo "== Source quality gate =="
./scripts/quality.sh

echo "== Build distributions =="
uv build --out-dir "$TEMP_DIR/dist"

shopt -s nullglob
wheels=("$TEMP_DIR"/dist/*.whl)
if ((${#wheels[@]} != 1)); then
  echo "ERROR: expected exactly one wheel, found ${#wheels[@]}" >&2
  exit 1
fi

echo "== Install wheel in an isolated environment =="
uv venv "$TEMP_DIR/venv"
uv pip install --python "$TEMP_DIR/venv/bin/python" "${wheels[0]}"

echo "== Smoke installed entry points =="
"$TEMP_DIR/venv/bin/lectos" --help >/dev/null
"$TEMP_DIR/venv/bin/lectos-tui" --help >/dev/null
"$TEMP_DIR/venv/bin/python" -c "from lectos import i18n; assert i18n.init('ru') == 'ru' and i18n.tr('Overview') != 'Overview'" 
"$TEMP_DIR/venv/bin/python" -m lectos --help >/dev/null

echo "Release check passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

command -v uv >/dev/null 2>&1 || { echo "ERROR: uv is required" >&2; exit 127; }

if (($# == 0)); then
  set -- lectos
fi

echo "== Vulture (advisory; review every finding) =="
uv run --locked --group audit vulture "$@" --min-confidence 80

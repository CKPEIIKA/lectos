#!/usr/bin/env bash
# Regenerate the roff man pages from their scdoc sources. Requires scdoc.
set -euo pipefail
cd "$(dirname "$0")/../man"
for page in lectos lectos-tui; do
  scdoc < "$page.1.scd" > "$page.1"
  echo "built man/$page.1"
done

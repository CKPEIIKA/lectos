#!/usr/bin/env bash
# Install the man pages for the current user (no sudo): afterwards `man lectos` works.
set -euo pipefail
dest="${XDG_DATA_HOME:-$HOME/.local/share}/man/man1"
mkdir -p "$dest"
cp "$(dirname "$0")/../man/lectos.1" "$(dirname "$0")/../man/lectos-tui.1" "$dest/"
echo "installed to $dest"

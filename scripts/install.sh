#!/usr/bin/env bash
# Install lectos for the current user from this checkout (no sudo): `lectos` and `lectos-tui` land in ~/.local/bin.
# Run it again after `git pull` to update. PyGObject and Poppler come from the system, hence --system-site-packages.
# LECTOS_PYTHON selects another interpreter, which must be able to import gi (PyGObject).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
pipx install --force --python "${LECTOS_PYTHON:-/usr/bin/python3.13}" --system-site-packages "$root"
"$root/scripts/install_man.sh"

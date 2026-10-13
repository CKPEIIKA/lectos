#!/usr/bin/env bash
# Rebuild slides.pdf from slides.tex without leaving LaTeX build files in the repository.
set -euo pipefail
cd "$(dirname "$0")"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
latexmk -pdf -interaction=nonstopmode -halt-on-error -no-shell-escape -outdir="$tmp" slides.tex
cp "$tmp/slides.pdf" slides.pdf

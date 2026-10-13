# TODO

Unfinished work only. Keep tasks concrete, prioritized, and verifiable. Move completed work to `DONE.md`.

## P1: presenter features

- [ ] Layout: user-defined arrangements beyond compact/wide (which panes where), and a layout for a vertical portrait screen.
- [ ] Test with a real second monitor and a pen: fullscreen placement, pressure, eraser end, latency on heavy figures.
- [ ] Ink: keep it attached to the right slide when the deck is recompiled and slides move (match by slide text), eraser by area instead of whole strokes, and shapes (line, arrow, rectangle).

## Terminal console follow-ups

- [ ] Kitty/Sixel previews (`chafa -f kitty|sixel`) when the terminal supports them, with a safe capability check that does not read the terminal.
- [ ] Terminal console: render math notes as images in Kitty-capable terminals; mouse support; a way to aim a laser from the terminal.
- [ ] Zathura projector: blackout (a reliable method), chalkboard-less ink via `HighlightRects`, presentation mode toggle; test `fullscreen` on a real second monitor.
- [ ] Optional `--projector` autodetection: use Zathura when GTK is missing.

## Unprioritized

- [ ] Timing statistics: time spent on each slide, broken down by sections.

## Follow-ups


- [ ] Filmstrip: mark section boundaries; keep the viewed slide centred when more are requested than fit.
- [ ] Let the user hide whole menu sections and rename header groups in `options.toml` (the header is already configurable).

- [ ] Beamer notes: `\begin{note}` environments, `\note<N>` overlay-specific notes, `\input` of other .tex files, and a visible warning when the frame count differs from the `.nav` page map.
- [ ] Typst notes input.

- [ ] Align inline formula images to the text baseline (use `dvipng --depth*`), and fit display formulas wider than the pane.
- [ ] Notes Markdown: tables, nested lists, code blocks, footnotes, images; or a Pandoc-to-PDF notes mode.
- [ ] Notes sections relative to long notes: next/previous section keys, outline.
- [ ] Search: highlight hit rectangles on slides (`Poppler.Page.find_text`).
- [ ] Lazy or cached overview thumbnails for very long decks (411 widgets today).
- [ ] Tests for `PdfDoc`, `ConsoleWindow` and `ProjectorWindow` behavior under a headless GTK display.
- [ ] A control channel (`lectosctl`) so other tools or key bindings can drive a running session.

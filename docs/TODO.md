# TODO

Unfinished work only. Keep tasks concrete, prioritized, and verifiable. Move completed work to `DONE.md`.

## P0: Xournal++/pympress-style conveniences (each one configurable in `options.toml` and, where it is a console setting, in Settings)

- [x] Shape tools: line, arrow, rectangle, ellipse (`shape`, `[drawing] shape`).
- [ ] Always-visible pen palette: colours, widths, tool buttons (pen, highlighter, eraser, shape) on the main screen; `[console] palette = true|false` and `[drawing] palette = [colours]`.
- [ ] Text boxes on a slide (`text` tool): placed with a click, stored as ink, exported.
- [ ] Select, move and delete strokes (`select` tool) with undo.
- [ ] Zoom/magnifier on the audience screen (`zoom` command, key, `[projector] zoom_factor`).
- [ ] Page-number box in the header: type a slide number or click to jump (`goto` item exists in the header table; make it an entry).
- [ ] Per-slide timers: time spent on each slide, shown in the overview (`[console] slide_timers`).
- [ ] Embedded media playback from the PDF (videos), opt-in `[console] media`.
- [ ] Rebindable keys (`[keys]` table) and Settings fields for notes file names and the palette.
- [ ] Pen pressure curve (`[drawing] pressure`), tablet button mapping, palm rejection option.

## P1: presenter features

- [ ] Layout: user-defined arrangements beyond compact/wide (which panes where), and a layout for a vertical portrait screen.
- [ ] Test with a real second monitor and a pen: fullscreen placement, pressure, eraser end, latency on heavy figures.
- [ ] Ink: keep it attached to the right slide when the deck is recompiled and slides move (match by slide text) and eraser by area instead of whole strokes.

## Terminal console follow-ups

- [ ] Kitty/Sixel previews (`chafa -f kitty|sixel`) when the terminal supports them, with a safe capability check that does not read the terminal.
- [ ] Terminal console: render math notes as images in Kitty-capable terminals; mouse support; a way to aim a laser from the terminal.
- [ ] Zathura projector: blackout (a reliable method), chalkboard-less ink via `HighlightRects`, presentation mode toggle; test `fullscreen` on a real second monitor.
- [ ] Optional `--projector` autodetection: use Zathura when GTK is missing.

## Unprioritized

- [ ] Notes on separate PDF pages (`\setbeameroption{show notes}`) and a separate notes PDF; embedded video/media.

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

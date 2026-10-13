# LECTOS(1)

## NAME

`lectos` - GTK4 presenter console and projector window for PDF slides with Markdown/LaTeX lecture notes

## DISCLAIMER

This project is vibe-coded. Treat documented support boundaries and quality gates as the source of truth, and verify behavior for your use case.

## SYNOPSIS

```text
lectos [--console gtk|tui] [--projector gtk|zathura|none] [--layout auto|compact|wide] [--lang auto|en|ru|de] [--config OPTIONS.toml] [--windowed] [--monitor N] [--fullscreen] [--no-vim] PDF [NOTES.md|NOTES.tex]
lectos-tui [same options] PDF [NOTES.md|NOTES.tex]      # terminal console, Zathura projector, no GTK
```

## DESCRIPTION

`lectos` has two independent parts: the **projector** (what the audience sees) and the **console** (what you work with: current, projected and next slide, timer, overview, search and scrollable notes). Pick each separately with `--console` / `--projector` or `[ui]` in `options.toml`; flags beat the options file, which beats the entry point's default.

![The wide layout on a big screen: slide with ink and laser, audience and next previews, notes with typeset math, and the filmstrip](docs/screenshots/wide.png)

| Compact layout with the search panel open | What the audience sees |
|---|---|
| ![The compact layout for a notebook, with search results above the slides](docs/screenshots/compact.png) | ![The projector window: the slide with the red ink circle](docs/screenshots/projector.png) |

| console \ projector | `gtk` (our window) | `zathura` | `none` |
|---|---|---|---|
| `gtk` (default for `lectos`) | everything | slides only | slides only |
| `tui` (default for `lectos-tui`, with `zathura`) | notes, search, timer, freeze, blackout, chalkboard, ink tools | notes, search, timer, freeze | notes only |

- **gtk projector**: our window; supports blackout screen (picture/text), chalkboard, ink, laser. Needs GTK 4, PyGObject and the Poppler typelib.
- **zathura projector**: a plain Zathura window driven over D-Bus (`gdbus`); follows the deck, freeze works, fullscreen via `fullscreen`. It cannot show blackout, chalkboard, ink or laser, so those commands answer "not supported by this projector".
- **gtk console**: all features below, including drawing and the laser on the preview. Needs GTK as above.
- **tui console** (`lectos-tui`, or `--console tui`): standard-library Python in the terminal, no GTK unless combined with the gtk projector. Slide previews use `pdftoppm` and `chafa` (Unicode block characters; skipped in terminals narrower than 90 columns or when the tools are missing). Notes are shown as styled text; math is approximated with Unicode (`∂ₜ U + ∇·F(U) = S(U)`), not typeset. Overview and search results are lists. It has no laser, no `show-slide`, no mouse; with the gtk projector you can still draw on the projector window with a pen (or a mouse after `draw on`). Keys are always vim-style plus arrows; `:` opens the command line with Tab completion; `:q` quits (Ctrl-C also saves and quits). `?` or `:help` opens a list of every command usable with this projector (usage, description, key; commands that need the GTK console or a projector with more features are marked); Enter on an entry starts typing it, and `:help NAME` describes one command. With the gtk projector, GTK's own messages are written to `$XDG_STATE_HOME/lectos/<id>.log` so they cannot garble the screen.

The GTK console opens a console window; with the gtk projector it also opens the projector window. It follows the GNOME design guidelines through libadwaita (1.4 or newer): a toolbar view with header bar, banners, toasts and boxed lists, and it follows the system light/dark setting. State the audience cares about is always visible: **banners** at the top say when the projector is frozen (with the slide it is stuck on), blacked out, or showing the chalkboard, each with a button to undo it; the matching header toggles light up (blackout in red); the footer shows the current pen, eraser, laser and board. Messages appear as toasts. The footer's right side shows how you stand against the plan (`on time`, `ahead 2:10`, `behind 3:40`: every slide gets an equal share of the lecture length and a slide's own share counts as on time), the estimated finish time at your current pace (`ends 15:48`), and the clock. `help` (key `?`) opens a page listing every command with usage and key; pick a row to start typing it.

Notes are either a Markdown file or a Beamer `.tex` file. In Markdown, `<!-- slide: N -->` markers tie sections to slides. In a `.tex` file, every `\note{...}` is taken as the notes of the frame it belongs to (inside the frame, or right after it), with the frame title as heading. lectos never compiles LaTeX for slides: build the PDF yourself, then `lectos slides.pdf slides.tex`. Page numbers come from the `.nav` file Beamer writes next to the `.tex` or the PDF; without it frame N is taken as slide N, which is wrong when frames have overlays. Converted note markup: `itemize`/`enumerate`/`\item`, `\textbf`, `\alert`, `\emph`, `\textit`, `\texttt`, `\\`; other commands are shown as written. In both cases the console scrolls to and highlights the section of the current slide. Supported Markdown: `#`-`###` headings, `**bold**`, `*italic*`, `` `code` ``, `-` bullets. Math (`$..$`, `$$..$$`, `\[..\]`) is compiled with LaTeX and dvipng into cached images; a formula that fails to compile stays visible as raw TeX. Tables, nested lists, code blocks and footnotes are not rendered yet.

Console features: go to slide, thumbnail overview, search across slide text and notes, timer (elapsed, left, estimated at current pace), freeze (hold the projector while browsing privately), blackout, fullscreen for either window, resizable panes, and recovery of page, timer, notes position and layout after a restart.

GTK console layouts (`layout` command, `--layout`, `[console] layout`, or View > Layout in the menu):

- **compact** (notebook): large slide, small audience and next previews below it, notes on the right.
- **wide** (big screen, e.g. Full HD): large slide, bigger audience and next previews, tall notes, and a **filmstrip** along the bottom with the previous slides (default 3) and the next ones (default 8, up to 16; `upcoming N`, `previous N`). Click a thumbnail to go there; the viewed slide is outlined and a red dot marks what the audience sees now.
- **auto** (default): wide from about 1500 px window width, back to compact below about 1380 px.

The header bar uses symbolic icons (with a text fallback when the icon theme lacks one) and is configurable: `[header]` in `options.toml` lists the items on the left (`start`), the middle (`title`: `timer`, `slide` or `none`) and the right (`end`). Items: `prev next goto overview search freeze blackout board laser draw eraser undo redo projector fullscreen layout menu`. The menu button opens a standard GTK 4 menu that contains every action, including those you leave out of the header, so the header can be as sparse as you like. Everyday actions are inline (slides, freeze, blackout, chalkboard, fullscreen, layout); the rest is grouped under **Tools** (Timer, Drawing, Laser pointer, chalkboard background) and **View** (layout, upcoming slides), each with check and radio items and key hints.

**Search** opens a panel above the slides: the slide, notes and filmstrip stay visible while you type and step through hits (`n`/`N`, or click a result); Esc or the search button closes it. In the terminal console the results are a panel at the bottom, not a full-screen list. The **overview grid**: a click looks at a slide (the projector stays put), a double click goes there and returns to the slides, and Esc or the grid button again cancels and restores the slide you were on.

**Lecture length** is free: `target 90`, `target 1h30`, `target 1:30` or `target 45m` (1 minute to 24 hours), Timer > Custom length… in the menu, or `target_min` in `options.toml` (a number or the same forms). It is saved with the session.

**Languages**: English, Russian and German. The language comes from `LC_ALL`/`LANGUAGE`/`LANG`, or `[ui] language = "de"`, or `--lang de`. Buttons, tooltips, menus, banners, messages and the help text are translated; your notes and slides are not. Translations are plain gettext `.po` files in `lectos/locale/` read at start-up (no build step); to add a language copy `ru.po` to `<code>.po`, translate the `msgstr` lines and add the code to `LANGUAGES` in `lectos/i18n.py` (and to the `--lang` choices in `lectos/cli.py`). `scripts/marked_strings.py` lists every string marked for translation, and a test fails when a marked string has no translation or a translation changes a `{placeholder}`.

Everything the interface can do is also a command on the `:` line (`:` with vim keys on, or the options menu). Tab completes command names (`:fr<Tab>` gives `:freeze `, several matches are listed); `:help` lists all. Buttons, keys and the `:` line share one command table: `next [n]`, `prev [n]`, `goto N` (or just `:N`, `:$`), `first`, `last`, `scroll-down [n]`, `scroll-up [n]`, `search [text]`, `hit-next`, `hit-prev`, `show-slide [on|off]`, `overview`, `main`, `freeze [on|off]`, `blackout [on|off]`, `timer`, `timer-reset`, `target MIN`, `fullscreen [on|off]`, `projector-fullscreen [on|off]`, `vim [on|off]`, `layout auto|compact|wide|toggle`, `upcoming N`, `previous N`, `help [COMMAND]`, `clear`, `undo`, `redo`, `draw [on|off]`, `eraser [on|off]`, `color C`, `width N`, `board [on|off]`, `laser [on|off]`, `help`, `quit`.

Keys (arrows, Space, PageUp/PageDown, Home/End always work; vim keys are optional):

| key | action |
|---|---|
| `l` / `h` | next / previous slide (count allowed: `5l`) |
| `j` / `k` | scroll notes |
| `gg`, `G`, `12G` | first, last, slide 12 |
| `:` | command line (Tab completes) |
| `:12`, `:$` | go to slide |
| `/`, `n`, `N` | search, next hit, previous hit |
| `f` / `F` | projector / console fullscreen |
| `b`, `z`, `o`, `t` | blackout, freeze, overview, timer |
| `d`, `e`, `u`, `U`, `B`, `p` | mouse drawing, eraser, undo, redo, chalkboard, laser |

Drawing, laser and chalkboard: draw on the large preview in the console with a pen (the eraser end erases); a mouse draws only after `draw on`. Ink belongs to the slide you are looking at and is stored per page; the chalkboard (`board`) has its own ink, so slide ink and board ink never mix. Everything is configurable, in `options.toml` (`[drawing]`, `[laser]`) and while presenting:

- pen: `color`, `width`, `highlighter` (wide translucent strokes; `highlight-alpha`), `smooth 0..5` (smooths finished strokes), `eraser-size`, `draw`, `eraser`
- history: `undo`, `redo`, `clear` (this slide or the board), `clear-all` (**every** slide and the board; a toast offers Undo, and `restore-all` brings it back), `export [FILE]` (the slides with your ink as a new PDF, plus a final page for the chalkboard if it has ink; an existing file is never overwritten, a `-2` name is used instead)
- chalkboard: `board`, `board-style chalk|black|white|ruled|grid`
- laser: `laser` (the dot follows the pointer over the large preview and shows on the projector), `laser-color`, `laser-size 3..30`, `laser-style dot|ring|cross`

Keys: `d`, `e`, `u`, `U`, `B`, `p`. Ink is saved in `$XDG_STATE_HOME/lectos/` next to the recovery state and restored on restart; it is tied to page numbers, so recompiling a deck with moved slides moves the ink with the numbers, not the content.

In the projector window: `f`/F11 fullscreen, `b` blackout, `c` clear ink on the shown layer, Escape leaves fullscreen, and a pen or `draw on` mouse also draws there.

Options live in `$XDG_CONFIG_HOME/lectos/options.toml` (or `--config FILE`); a missing default file means defaults, unknown keys are errors. The blackout screen can show a picture and/or text instead of plain black:

```toml
[blackout]
image = "standby.svg"      # relative to this file, absolute, or ~/...; any format GTK can load
text = "Please stand by…"
background = "#101820"     # #rrggbb
text_color = "#f2f2f2"

[console]
vim = true                 # vim keys on at startup (--no-vim overrides)
target_min = 90            # default timer target

[ui]
console = "gtk"            # or "tui"
projector = "gtk"          # or "zathura"
```

See `examples/options.toml` and `examples/standby.svg`. Status: tested with unit tests and by driving both windows on GNOME/Wayland with a 6-page and a 411-page PDF. Not tested: real pen pressure and the eraser end, fullscreen on a second monitor, a real lecture. With one monitor the projector stays windowed.

## QUICK START

Requires Python 3.13 or newer and uv. Depending on the combination: PyGObject with GTK 4 and Poppler typelibs, plus libadwaita 1.4+ for the GTK console (gtk console or gtk projector); `latex` plus `dvipng` (math images in the gtk console); `zathura` and `gdbus` (zathura projector); `pdftoppm`, `pdftotext` and optionally `chafa` (terminal console).

PyGObject is taken from the system, so create the environment with system site packages:

```bash
uv venv --system-site-packages --python /usr/bin/python3.13
uv sync --locked
uv run lectos examples/slides.pdf examples/slides.tex   # Beamer \note{} commands as notes
uv run lectos examples/slides.pdf examples/notes.md     # the same notes as Markdown
uv run lectos-tui examples/slides.pdf examples/slides.tex   # terminal console + Zathura projector, no GTK
uv run lectos --console tui --projector gtk examples/slides.pdf examples/slides.tex   # terminal console, our window
```

`examples/` holds a sample deck about lectos itself: `slides.tex` (Beamer, with notes), the compiled `slides.pdf`, and `notes.md`. Rebuild the PDF with `examples/build.sh`.

## FILES

- `AGENTS.md` - common engineering contract and project-specific rules
- `TODO.md` - unfinished work only
- `DONE.md` - completed outcomes and validation evidence
- `pyproject.toml` - package, dependency, pytest, Ruff, and Ty configuration
- `lectos/` - import package; see the layer map in `AGENTS.md`
- `examples/` - sample deck about lectos: Beamer source with notes, compiled PDF, Markdown notes, `options.toml`, `standby.svg`
- `tests/` - automated tests
- `docs/README.md` - documentation map; `docs/screenshots/` - the pictures above
- `man/` - manual pages (scdoc sources and generated roff)
- `scripts/quality.sh` - local quality gate
- `scripts/audit.sh` - optional local dead-code audit
- `scripts/release_check.sh` - manual distribution and installed-CLI gate

## DEVELOPMENT

```bash
uv sync --group dev
./scripts/quality.sh
```

The gate runs Ruff linting, Ruff formatting checks, Ty, and pytest. Run Vulture manually when reviewing removals: `./scripts/audit.sh`.

## LICENSE

Copyright (C) 2026 the lectos authors.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License, version 3 only, as published by the Free Software Foundation. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE) for the full text (SPDX: `GPL-3.0-only`).

Nothing from other projects is bundled. lectos uses, as separate programs or dynamically loaded libraries, GTK 4, libadwaita, PyGObject and pycairo (LGPL), Poppler (GPL), Zathura (zlib), chafa (LGPL), LaTeX and dvipng. The sample deck and the kitty drawing in `examples/` were written for this project and carry the same license.

## MANUAL PAGE

`man/lectos.1` and `man/lectos-tui.1` are short references to the options, keys and files. Read one without installing: `man -l man/lectos.1`. Install for your user (no sudo): `./scripts/install_man.sh`, then `man lectos`. They are written in scdoc (`man/*.scd`); regenerate the roff with `./scripts/build_man.sh`. A test checks that every command-line option is documented and that the roff matches its source.

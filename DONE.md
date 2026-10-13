# DONE

Completed work only. Record meaningful outcomes and validation evidence, newest first.

## 2026-10-13: PDF links, annotations, Beamer notes pages

- Clickable PDF links in the console preview and the projector window: page links go there (the projector follows), http/https/mailto open in the desktop's browser, anything else is never opened; inactive while drawing, on the board and for pen input.
- Text annotations of the PDF become read-only notes when no notes file is given.
- Beamer `show notes on second screen` decks (slide and notes side by side) are detected (`--notes-pages auto|none|left|right`, `[console] notes_pages`): the audience, previews, search and links see the slide half, the notes half is shown in the notes pane. Zathura as projector triggers a warning.
- Tests build small PDFs by hand (no LaTeX needed); 473 tests, 100% coverage. README credits pympress as the inspiration.

## 2026-10-13: start window, notes editing, settings, drawing layout; subpackages; 100% coverage

- `lectos` without arguments opens a start window (choose slides, notes, or a folder); a PDF or a folder on the command line works too, and notes next to the slides are found automatically. `Open other slides…` / `:open` switches decks without leaving the application (state of the old deck is saved first).
- Notes can be edited in the console (`edit`, key `E`): Markdown is rewritten atomically (one slide's section), a Beamer `.tex` is never touched (edits live in the state folder).
- Settings window and `panel NAME [on|off]` / `[console] hide`: notes, audience, next, filmstrip and status bar can be hidden; saved with the session.
- Quick drawing layout (`sketch`, key `s`, header button, `layout draw`): large slide plus a toolbar (colours, width, highlighter, eraser, undo, redo, clear, board, laser); the mouse draws while it is on. Pointer is a crosshair (cell for the eraser) wherever the mouse draws, in both windows.
- `export-ink` writes a slide's (or the board's) drawing layer alone to a transparent PNG.
- Distinct window titles and icons for console and projector (bundled SVGs). Overview tiles keep their height; the timer button has room.
- README shortened to install/run/basics; the full reference moved to `docs/usage.md`.
- Package split into subpackages with at most 7 Python files per folder (enforced by a test); 100% line and branch coverage gate (446 tests; the GTK tests need a display). Validation: `./scripts/quality.sh`, `./scripts/release_check.sh`.

## 2026-10-13: ultrareview findings fixed

- Ink recovery file: a stroke colour like `#zzzzzz` or `#abc` was accepted and then crashed every redraw and PDF export; colours are now validated as `#rrggbb` when loading.
- `restore-all` could undo the wrong thing: after `clear-all`, drawing a new stroke (or undoing by hand) on a cleared layer left that layer marked as restorable. Any later change to a layer now cancels its pending restore.
- Terminal console: `restore-all` was missing from its command table; a test now requires every capability-gated command to be registered or marked GTK-only.
- Terminal + GTK projector: a startup failure (e.g. `pdfinfo` missing) left the process hanging with the projector window open; it now quits with the error message (checked in a pseudo-terminal).
- Terminal input: a UTF-8 character split across two reads (long pastes of Russian or German text) was silently dropped; keys are now decoded with an incremental decoder.
- Each fix has a regression test (250 tests).

## 2026-10-13: license, man pages, screenshots; dark-theme fixes

- `LICENSE` is now the canonical GPL-3.0 text (it carried a kernel-style SPDX preamble); README has the standard notice, a note on third-party software, and the license is `GPL-3.0-only` in `pyproject.toml`.
- Short man pages `lectos(1)` and `lectos-tui(1)` (scdoc sources + generated roff), `scripts/build_man.sh`, `scripts/install_man.sh` (user-local, no sudo). Tests: every CLI option is documented, the roff matches its source.
- README screenshots (`docs/screenshots/`: wide layout, compact layout with search open, the audience view) rendered from the real windows in the stock light theme.
- Found while taking them: formula images in the notes were black on transparent, unreadable on dark themes: they are now compiled in the notes' text colour and recompiled when the theme changes; the running-timer highlight made the timer unreadable in the light theme: it now uses the accent text colour.

## 2026-10-13: German, schedule in the footer

- German added (`de.po`, `--lang de`, `[ui] language = "de"`, `LANG=de_*`); the i18n tests now run over every catalog file and check that each language has one.
- The footer's dotted "pace · clock" is replaced by information that helps during a lecture: ahead/behind the plan (every slide gets an equal share of the length; its own share is on time), the estimated finish time at the current pace, and the clock. Same text in the terminal status line. The pen/laser summary uses commas instead of dots.

## 2026-10-13: Russian, inline search, grid clicks, grouped menu, custom lecture length

- Basic localisation: English and Russian via plain `.po` files read at start-up (`[ui] language`, `--lang`, `LANG`); menus, tooltips, banners, toasts, help texts and the terminal console are translated. Tests keep the catalog complete (no marked string without translation, no stale entries, same placeholders, valid per `msgfmt`).
- Search is a panel above the slides in the GTK console (slides, notes and filmstrip stay visible) and a bottom panel in the terminal console; hits can be stepped through without closing it.
- Overview grid: click looks, double click goes and returns, Esc or the button again cancels and restores the previous slide.
- Menu regrouped: everyday actions inline, Timer / Drawing / Laser pointer as submenus under Tools, view options under View (about 20 top-level entries instead of 45).
- Lecture length can be anything from one minute to 24 hours: `target 90 | 1h30 | 1:30 | 45m`, Timer > Custom length…, `target_min` in options as a number or such a string.
- Validation: quality gate passes (223 tests, including GUI tests for the search panel, grid behaviour, menu structure and a console running in Russian). Rendered the Russian console with the search panel open and the frozen banner. Not tested: translation quality by a native reader beyond my own review; the grid with a pen or touch.

## 2026-10-13: libadwaita design, visible state, configurable drawing and laser, help

- GTK console rebuilt on libadwaita: toolbar view, header bar, **banners** for frozen / blackout / chalkboard (with a button to undo each), highlighted header toggles, footer summary of pen/eraser/laser/board, toasts for messages (erase-all offers Undo), boxed-list search results, an Adwaita-style help page; follows the system light/dark setting.
- Drawing and laser are configurable (`[drawing]`, `[laser]`, and commands): colour, width, highlighter + opacity, smoothing, eraser size, board backgrounds (chalk, black, white, ruled, grid), laser colour/size/shape; erase-all (`clear-all`, undoable via `restore-all`/toast); export of annotated slides to PDF (never overwrites).
- Help: `commands.HELP` documents every command; terminal `:help` is a pick-to-type list (marks what needs GTK or a richer projector), GTK `help` is a page; `help NAME` describes one command.
- Menu contains every action (navigation, drawing submenus, laser, view) so header items can be moved out freely; the window re-picks its layout and re-aligns the notes after resizes.
- Validation: quality gate passes (178 tests, including GUI wiring tests that check every menu entry points at a registered action, every header item builds, banners, toasts, layouts; skipped without a display). Rendered the real window to images: banners, highlighted toggles, grid board with ring laser, Undo toast, help page.

## 2026-10-13: layouts, icons, native menu, configurable header

- GTK console layouts: compact (notebook) and wide (big screen: larger previews, tall notes, filmstrip with previous and up to 16 upcoming slides), chosen automatically by window width or by `layout`/`--layout`; layout, counts and split positions are saved.
- Header bar uses symbolic icons with text fallback and is configurable (`[header]` start/title/end); the hamburger menu is a native `Gio.Menu` (sections, check/radio items, key hints) backed by `Gio.SimpleAction`s that mirror real state; entries the projector cannot do are greyed out.
- Fixed: after a layout rebuild the notes were not realigned to the current slide; the wide layout's split ignored the real window width until dragged.
- Validation: quality gate passes. Rendered the real windows to images (both layouts, and the menu popover) and checked them; scripted checks of layout switching, auto at full size, count clamping, saved state.

## 2026-10-13: terminal console and selectable projector/console

- Console and projector are independent: `--console gtk|tui`, `--projector gtk|zathura|none`, `[ui]` in `options.toml`; entry points `lectos` and `lectos-tui` (terminal console + Zathura, no GTK). Four combinations, plus `none`.
- New: `projection.py` (protocol, capabilities, `ProjectorSync`, command gating), `zathura.py`, `tui.py`/`tuitext.py`/`tuiterm.py`/`tuiglib.py`, `pdftools.py`, `unimath.py`. GTK console and terminal console share deck, timer, vim keys, commands, notes, search, ink and state.
- Bugs found by running it: `chafa` probes the terminal (5 s stall per call, and its replies would arrive as keystrokes) — now `--probe off --polite on` with stdin detached; Ctrl-C raised a signal instead of arriving as a key — ISIG off; GTK warnings garbled the terminal screen — stderr goes to a log file.
- Validation: quality gate passes (106 tests incl. terminal console state machine with a fake projector, key decoding, wrapping, Unicode math, capability gating, flag/config precedence). Real runs: terminal console + Zathura in a pseudo-terminal (Zathura's page checked over D-Bus after next/freeze/unfreeze/goto/overview), terminal console + our GTK window (board, blackout, colour, clean exit, no leaked warnings), GTK console with Zathura, with our window and with no projector (gated commands answer correctly). Not tested: Zathura fullscreen visually, a real second monitor, Kitty/Sixel terminals.

## 2026-10-13: ink, laser, chalkboard

- Persistent ink (per slide and a separate board layer) with undo/redo, eraser (stroke-wise), colour and width, saved to its own file under the XDG state directory; laser pointer driven by the pointer over the console preview; chalkboard toggle. Drawing happens on the console preview (pen, or mouse after `draw on`) and shows on the projector.
- One `Stage` draws slide/board, ink and laser for both windows. New commands: draw, eraser, undo, redo, color, width, board, laser (plus `clear` now per layer); keys d e u U B p.
- Validation: quality gate passes (64 tests: ink store incl. undo/erase/malformed load, pixel tests of the cairo drawing, stage coordinates, deck board/laser, separate ink state file). Scripted run of both windows: strokes, undo/redo, laser, chalkboard, bad colour/width messages, ink and board restored after restart; screenshots checked for console preview, audience thumbnail and projector. Not tested: real pen pressure and eraser end.

## 2026-10-13: commands, header bar, options.toml

- Fixed crash: `GestureDrag` has no `get_device_tool`; pen vs mouse is now decided from the event device.
- One command table for buttons, keys and the `:` line (24 commands) with Tab completion and `:help`; Tab no longer moves focus in the command line.
- Console layout: header bar with navigation, timer, freeze/blackout and an options menu; captions on the audience/next previews; footer with status, command line and pace/clock.
- `options.toml`: blackout picture/text/colours, vim default, timer target; `--config`; strict validation. Sample kitty `standby.svg`.
- Validation: quality gate passes (48 tests). Scripted run: every key action maps to a command, Tab completion, freeze/unfreeze, mouse-drag path, search and options via `execute`; screenshot of the kitty blackout screen checked. Not tested: real pen events.

## 2026-10-13: sample deck and Beamer notes

- `examples/` with a Beamer deck about lectos (8 frames with `\note{}` commands), its compiled PDF, `build.sh`, and equivalent Markdown notes.
- A `.tex` notes argument extracts `\note` commands per frame (titles as headings, itemize/emphasis converted), maps frames to pages via `.nav` or assumes one page per frame; lectos does not compile.
- Validation: quality gate passes (30 tests, including sample-deck page alignment for both formats). Ran the console on the sample with `.tex` and `.md` notes and checked screenshots.

## 2026-10-13: all-GTK rewrite

- Dropped Zathura/Evince/Sioyek, the HTTP server and the browser console. One GTK4 process with a projector window and a console window.
- Done from the backlog: timer (elapsed/left/pace), go to slide (entry, `:N`, `NG`), thumbnail overview, search across slide text and notes, freeze and blackout, console and projector fullscreen, vim keys option, resizable panes, recovery state (page, view, freeze, timer, notes scroll, pane, vim), notes with Markdown styling and LaTeX math as cached images.
- Validation: quality gate passes (Ruff, Ty, 22 tests including a latex/dvipng integration test). Scripted run of both windows on GNOME/Wayland: goto, freeze/unfreeze, preview-only search hits, overview, state file written; screenshots checked for rendering, highlights and math. A search test caught phrases spanning line breaks; a timer test caught a malformed save altering `running`. Not tested: second monitor, pen pressure, a real lecture.

## 2026-10-13: GTK4 projector prototype (superseded)

- `lectos/projector.py` window process plus `gtkview.py` backend (`--viewer gtk`); project moved to Python 3.13.
- Validation: quality gate passes. Manual: window rendered page 41 of a 411-page Russian/math PDF correctly (screenshot); `/api/goto` including clamping and clean shutdown work. Ink input and fullscreen on a second monitor not tested.

## 2026-10-13: first draft

- Project layout copied from `python-project-template`, renamed to `lectos`.
- Zathura backend, session, notes pipeline and browser console implemented.
- Validation: quality gate passes (Ruff, Ty, 3 tests). Manual: with a real Zathura and an Evince, `/api/state` and `/api/goto` moved the viewer; Pandoc produced MathML notes. Evince page movement not visually confirmed; sioyek untested.

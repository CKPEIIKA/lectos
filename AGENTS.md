# AGENTS.md

<!-- BEGIN COMMON ENGINEERING CONTRACT -->

This common engineering contract is mandatory for agents and contributors.
Project-specific rules may refine runtime versions, tool targets, architecture, protocols, and domain invariants, but may not weaken this contract silently.

## Common mission

Build small, deterministic Python software with explicit boundaries, stable behavior, and no hidden mechanisms.
Keep documentation aligned with actual behavior.

## Common principles

1. Prefer simple, direct implementations over frameworks and speculative abstractions.
2. Build strong domain modules instead of helper sprawl or convenience-wrapper layers.
3. Keep dependencies directional and domain logic independent of presentation, transport, storage, and external services.
4. Prefer composition, explicit data flow, explicit return types, and explicit errors.
5. Keep behavior and output deterministic. Do not add hidden network calls, silent fallbacks, or fake support claims.
6. Use one canonical path for each operation; different interfaces must reuse it.
7. Prefer deleting obsolete paths over adding compatibility shims.
8. Add a dependency only when it removes real complexity.
9. Keep changes minimal, focused, reviewable, and reversible.
10. Preserve user data and backward compatibility unless an intentional breaking change is documented.
11. Keep replies, comments, and commit messages concise, factual, and free of praise or filler.
12. Do not reformat, annotate, or refactor unrelated code while making a focused change.

## Common architecture rules

1. Each module owns one responsibility and one reason to change.
2. Public APIs are small, stable, typed, and documented where behavior is not obvious.
3. Avoid global mutable state, utility dumping grounds, import-time side effects, and cross-layer shortcuts.
4. Split modules when responsibilities diverge, not merely to satisfy a size metric.
5. Add an abstraction only after real uses establish a shared contract.
6. Keep project-specific boundaries and invariants in the project contract below.
7. Encapsulate low-level I/O, subprocesses, and protocols behind narrow boundary modules.
8. Do not bypass a layer or widen a private API without a documented reason and intentional design decision.

## Common Unix-style rules

1. Prefer plain files and stable, inspectable formats.
2. Send primary command output to stdout and diagnostics to stderr.
3. Make tools scriptable and non-interactive by default.
4. Do not overwrite user data without explicit authorization.
5. Do not write outside an explicitly selected output or state directory.
6. Make partial failure visible; never silently discard or invent data.

## Common Python rules

1. Default to Python 3.11 or newer. An explicit project contract may retain an older supported runtime.
2. Type public functions and data contracts, plus internal boundaries where inference is not obvious.
3. Prefer dataclasses or small typed records for data and explicit exceptions for failures.
4. Keep control flow readable and functions focused.
5. Use boring Python; avoid clever metaprogramming.
6. Use pathlib for paths and context managers for owned resources.
7. Prefer early returns and `continue` when they reduce nesting without obscuring the normal path.
8. Extract repeated or domain-significant literals into named constants or enums; keep obvious one-off values inline.
9. Use enums or typed values for multi-state modes; keep booleans for genuine binary options.
10. Comment non-obvious rationale, invariants, and trade-offs; do not narrate evident syntax.

## Common security and data rules

1. Never commit credentials, tokens, private data, proprietary fixtures, or machine-specific paths.
2. Read secrets from environment or settings, never source code.
3. Validate external input at boundaries.
4. Tests must not require private infrastructure or network access unless explicitly marked as integration tests.
5. Resolve user-controlled paths under an explicit allowed root, reject escapes, and account for symlinks before reading or writing.
6. Create temporary files with private, unpredictable names and replace durable outputs atomically when practical.
7. Pass subprocess arguments as a sequence without a shell; use a shell only when its syntax is the required interface and inputs are controlled.
8. Treat deserialization, archive extraction, and executable lookup as trust boundaries.

## Common reliability and resource rules

1. Put finite, documented timeouts on network, subprocess, lock, and external-service waits.
2. Bound input sizes, concurrency, queues, retries, and retained in-memory data where they can be influenced externally.
3. Propagate cancellation and interrupts promptly; clean up owned processes, files, locks, and connections on every exit path.
4. Retry only transient, idempotent operations with a bounded attempt count and backoff.
5. Test timeout, cancellation, partial-failure, and cleanup behavior for each boundary the project actually owns.

## Common quality gate

Use uv as the environment, dependency, and command runner.
A project contract may narrow the Ty target or add stricter checks, but may not omit these checks.

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

`uv run pytest` measures line and branch coverage and fails below 100% (`fail_under` in pyproject). GTK tests need a display; without one they are skipped and the gate fails.

Ruff must enable at least E, F, I, UP, B, SIM, C90, PLR, and RUF.
The shared line length is 120 and the shared complexity ceiling is 7.
Existing project-specific rules may be stricter.
Every exception must be narrow, documented beside its configuration, and removed when the debt is fixed.

## Common testing rules

1. Test public behavior and contracts rather than implementation trivia.
2. Add a regression test for each bug fix when practical.
3. Keep fixtures small, deterministic, and legal to redistribute.
4. Mark slow, network, hardware, benchmark, and integration tests.
5. Do not weaken assertions merely to make tests pass.
6. For reproducible bugs, add and observe a focused failing test before the fix, then run it and the common gate after the fix.

## Common documentation rules

1. Document supported behavior, limitations, inputs, outputs, and failure modes plainly.
2. Keep examples copy-pasteable and free of real secrets and private hosts.
3. Update architecture documentation when a boundary or public contract changes.
4. Distinguish supported, partial, experimental, and unsupported behavior.

## Common work-tracking rules

1. Keep the active backlog in `docs/TODO.md` and completed work in `docs/DONE.md`.
2. `docs/TODO.md` contains unfinished, concrete, and verifiable work; move meaningful completions to `docs/DONE.md`.
3. `docs/DONE.md` records outcomes and validation evidence, newest first.
4. A project contract may declare an operational path exception when tooling depends on it. `regression_vibe` retains `WIP/TODO.md` and `WIP/done.md` as that explicit exception.
5. Keep commit subjects concise, imperative, and without a period; explain context and rationale in the body for non-trivial changes.

## Common definition of done

A change is done when behavior is implemented, relevant tests and documentation are updated, mandatory quality checks pass, and no known contract mismatch is hidden.

<!-- END COMMON ENGINEERING CONTRACT -->

## Project contract

Mission: a small Linux presenter tool. Slides are PDFs; notes are Markdown or Beamer `\note{}`. Two independent choices: the projector (our GTK4 window drawn with Poppler and Cairo, or Zathura over D-Bus) and the console (GTK4, or a standard-library terminal UI). Each combination is one process.

Non-goals: compiling slides (the user builds the PDF; lectos only reads a Beamer .tex for its notes), slide authoring, a web UI, simulated keystrokes, controlling any viewer except Zathura through its D-Bus interface.

Package layout. **Keep package folders compact: no folder holds more than 7 Python files (counting `__init__.py`).** When a folder would grow past that, consolidate weak tiny modules or introduce a coherent subpackage. A test enforces it for `lectos/` and `tests/`. Dependencies point down this list; modules marked * need GTK/PyGObject (the rest import without it):

- `lectos/` - entry and cross-cutting modules only: `cli.py` (`lectos` / `lectos-tui` arguments, the console/projector choice, dispatch; imports GTK modules only when needed), `config.py` (`options.toml` loading and strict validation), `i18n.py` (gettext-style catalogs from `lectos/locale/*.po`; user-visible strings go through `tr("...")`, strings kept in tables through `noop("...")`; a test enforces that every marked literal is translated and placeholders match), `state.py` (recovery files under `$XDG_STATE_HOME/lectos`), `paths.py` (never-overwrite names, atomic writes, finding notes and slides in a folder)
- `lectos/model/` - presentation state and rules, no GUI: `deck.py` (page/view/freeze/blackout, `Timer`, schedule), `ink.py` (strokes per layer, tool, undo/redo, JSON), `style.py` (board backgrounds, laser look), `layout.py` (compact/wide/auto, filmstrip), `header.py` (header item table)
- `lectos/control/` - what the presenter can ask for, no GUI: `commands.py` (`:` parsing, flags, Tab completion, the help table), `keys.py` (vim keys), `toolcmds.py` (pen/board/laser settings shared by both consoles), `search.py`
- `lectos/notes/` - lecture notes: `markdown.py` (`NotesSource`, splitting, parsing into spans, replacing one slide's section), `beamer.py` (`\note{}` extraction, frame-to-page via `.nav`; edited notes are kept as Markdown in the state folder and never written to the `.tex`), `unimath.py` (LaTeX to Unicode), `mathimg.py` (LaTeX to cached PNG via `latex` and `dvipng`; a subprocess boundary)
- `lectos/draw/` - cairo drawing shared by both consoles, no GTK: `render.py` (strokes, laser, board), `stage.py` (what the audience sees: slide or board + ink + laser; PDF export)
- `lectos/projectors/` - `projection.py` (`Projector` protocol with capability set, `ProjectorSync`, command gating), `zathura.py` (Zathura over D-Bus)
- `lectos/gtk/`* - GTK console and window wiring: `app.py` (shared `Core`, projector choice, `Launcher`/`Session` that start and switch decks, polling, autosave), `console.py` (the presenter window), `projector.py` (the audience window), `inkinput.py` (pen/mouse gestures and the drawing cursor), `pdfdoc.py` (Poppler), `tuiglib.py` (terminal console inside a GLib loop when the projector is our GTK window)
- `lectos/gtk/widgets/`* - what the console opens or embeds: `start.py` (choose slides, notes or a folder), `settings.py` (what is shown), `notesedit.py` (edit one slide's notes), `drawbar.py` (toolbar of the drawing layout), `css.py` (shared stylesheet); bundled icons live in `lectos/gtk/icons/` (data, installed with the wheel)
- `lectos/term/` - terminal console, no GTK: `tui.py` (state machine: keys in, frame lines out), `tuitext.py` (ANSI wrapping), `tuiterm.py` (raw terminal, key decoding), `pdftools.py` (`pdfinfo`/`pdftotext`/`pdftoppm`/`chafa` boundary)
- `tests/` mirrors the packages (`tests/model/`, `tests/control/`, ...) with the same folder-size limit

Invariants: user-visible strings are literals passed to `tr()`/`noop()` (no f-strings, so they can be extracted: use `tr("... {x}").format(x=...)`); searching never replaces the slides (an inline panel), and the overview grid restores the previous view when cancelled; the GTK console is built from libadwaita widgets (`Adw.ApplicationWindow`, `ToolbarView`, `Banner`, `ToastOverlay`, `PreferencesPage`) and follows the system colour scheme; anything the audience would care about (frozen, blackout, board) has a banner, not only a toggle; every command has an entry in `commands.HELP` (a test enforces it) and appears in the GTK menu; pen/board/laser changes go through `Tools` so both consoles behave identically; export and erase-all never destroy data silently (unique file names; erase-all is undoable); header items and menu entries only call `ConsoleWindow.execute`, and widget state (toggles, check and radio items) is derived from the real state in `_sync_actions`, never stored in the widgets; the main page is rebuilt only when the resolved layout changes, and all layouts share one text buffer; the projector is only ever moved through `ProjectorSync` (deck subscription), never by a console directly; every console command that needs a projector feature is registered through `apply_caps`, so a projector without the capability answers "not supported by this projector" instead of silently doing nothing; the terminal console never lets `chafa` probe the terminal (`--probe off`) and receives Ctrl-C as a key (ISIG off); stderr is redirected to a log while the terminal screen is in use together with GTK; both GTK windows draw through one `Stage`, so the console preview and the projector cannot disagree; ink coordinates are in layer space (page points, or the 1600x900 board), the laser is stored as fractions of the shown content; every user action is a named command in the console's single command table (`ConsoleWindow.execute`); buttons, keys and the `:` line all go through it, so the `:` line can do everything the interface can; colours from options are validated as `#rrggbb` before they reach CSS; pages are zero-based internally and one-based only in notes markers and the UI; the projector page changes only through `Deck`; `Deck.peek` moves the view without the projector; GUI-free modules stay importable without PyGObject so they can be unit-tested; `latex` runs with `-no-shell-escape` and paranoid file access, with a timeout, and one bad formula never hides the others; state and cache files are written atomically or content-addressed; notes edits never modify a Beamer `.tex` (they go to the state folder) and rewrite a Markdown file atomically, one slide's section only; the drawing layout turns mouse drawing on and puts the earlier setting back when left; panels the user hides are only left out of the layouts (`hidden`), never destroyed state.

Environment: PyGObject comes from the system, so the venv is created with `--system-site-packages`; `ty` ignores unresolved imports only in the GTK modules, and Ruff ignores E402 there because `gi.require_version` must run first.

Extra gate: none beyond the common gate. Window behavior needs a manual run on a real two-monitor setup.

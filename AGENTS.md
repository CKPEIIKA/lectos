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

1. Keep the active backlog in root `TODO.md` and completed work in root `DONE.md`.
2. `TODO.md` contains unfinished, concrete, and verifiable work; move meaningful completions to `DONE.md`.
3. `DONE.md` records outcomes and validation evidence, newest first.
4. A project contract may declare an operational path exception when tooling depends on it. `regression_vibe` retains `WIP/TODO.md` and `WIP/done.md` as that explicit exception.
5. Keep commit subjects concise, imperative, and without a period; explain context and rationale in the body for non-trivial changes.

## Common definition of done

A change is done when behavior is implemented, relevant tests and documentation are updated, mandatory quality checks pass, and no known contract mismatch is hidden.

<!-- END COMMON ENGINEERING CONTRACT -->

## Project contract

Mission: a small Linux presenter tool. Slides are PDFs; notes are Markdown or Beamer `\note{}`. Two independent choices: the projector (our GTK4 window drawn with Poppler and Cairo, or Zathura over D-Bus) and the console (GTK4, or a standard-library terminal UI). Each combination is one process.

Non-goals: compiling slides (the user builds the PDF; lectos only reads a Beamer .tex for its notes), slide authoring, a web UI, simulated keystrokes, controlling any viewer except Zathura through its D-Bus interface.

Layers (dependencies point down; modules marked * need GTK):

- `cli.py` - `lectos` / `lectos-tui` arguments, the console/projector choice, dispatch; imports GTK modules only when needed
- `projection.py` - `Projector` protocol with capability set, `ProjectorSync` (deck to projector), command gating by capability; `zathura.py` - Zathura projector; no GTK imports
- `app.py`* - GTK console application: shared `Core`, projector choice, polling, autosave, close handling
- `console.py`*, `projector.py`* - the two windows; no business rules beyond wiring
- `deck.py` - page/view/freeze/blackout state and `Timer`; no GUI imports
- `keys.py` - vim key interpreter; `commands.py` - `:` line parsing, flags and Tab completion; both without GUI imports
- `ink.py` - strokes per layer (`s<page>` or `board`), tool, undo/redo, JSON round trip; `render.py` - cairo drawing of strokes, laser and board; `stage.py` - what the audience sees (slide or board + ink + laser); all without GTK imports
- `tui.py` - terminal console as a state machine (keys in, frame lines out; testable without a terminal); `tuitext.py` - ANSI wrapping and clipping; `tuiterm.py` - raw terminal and key decoding; `unimath.py` - LaTeX to Unicode; `pdftools.py` - `pdfinfo`/`pdftotext`/`pdftoppm`/`chafa` boundary; `tuiglib.py`* - terminal console inside a GLib loop when the projector is our GTK window
- `inkinput.py`* - pen/mouse gestures that draw or erase; used by both windows
- `i18n.py` - gettext-style catalogs (English source text; `ru`, `de`) read from `lectos/locale/*.po`; strings shown to the user are wrapped in `tr("...")`, strings kept in tables in `noop("...")` and translated where shown; a test enforces that every marked literal is translated and that placeholders match; no GUI imports
- `style.py` - board backgrounds and laser look; `toolcmds.py` - pen/board/laser settings as commands that return a message (shared by both consoles); `paths.py` - never-overwrite file names; all without GUI imports
- `layout.py` - compact/wide/auto rules, filmstrip page selection and thumbnail sizing; `header.py` - the table of header items (icons, fallback text, commands); both without GUI imports
- `config.py` - `options.toml` loading and validation (strict: unknown keys and bad values are errors); no GUI imports
- `notes.py` - `NotesSource` protocol, Markdown splitting and parsing into spans; `beamer.py` - `\note{}` extraction from .tex and frame-to-page mapping via `.nav`; `search.py` - substring search
- `mathimg.py` - LaTeX to cached PNG via `latex` and `dvipng`; the only subprocess boundary
- `pdfdoc.py`* - Poppler access; `state.py` - recovery file under `$XDG_STATE_HOME/lectos`

Invariants: user-visible strings are literals passed to `tr()`/`noop()` (no f-strings, so they can be extracted: use `tr("... {x}").format(x=...)`); searching never replaces the slides (an inline panel), and the overview grid restores the previous view when cancelled; the GTK console is built from libadwaita widgets (`Adw.ApplicationWindow`, `ToolbarView`, `Banner`, `ToastOverlay`, `PreferencesPage`) and follows the system colour scheme; anything the audience would care about (frozen, blackout, board) has a banner, not only a toggle; every command has an entry in `commands.HELP` (a test enforces it) and appears in the GTK menu; pen/board/laser changes go through `Tools` so both consoles behave identically; export and erase-all never destroy data silently (unique file names; erase-all is undoable); header items and menu entries only call `ConsoleWindow.execute`, and widget state (toggles, check and radio items) is derived from the real state in `_sync_actions`, never stored in the widgets; the main page is rebuilt only when the resolved layout changes, and all layouts share one text buffer; the projector is only ever moved through `ProjectorSync` (deck subscription), never by a console directly; every console command that needs a projector feature is registered through `apply_caps`, so a projector without the capability answers "not supported by this projector" instead of silently doing nothing; the terminal console never lets `chafa` probe the terminal (`--probe off`) and receives Ctrl-C as a key (ISIG off); stderr is redirected to a log while the terminal screen is in use together with GTK; both GTK windows draw through one `Stage`, so the console preview and the projector cannot disagree; ink coordinates are in layer space (page points, or the 1600x900 board), the laser is stored as fractions of the shown content; every user action is a named command in the console's single command table (`ConsoleWindow.execute`); buttons, keys and the `:` line all go through it, so the `:` line can do everything the interface can; colours from options are validated as `#rrggbb` before they reach CSS; pages are zero-based internally and one-based only in notes markers and the UI; the projector page changes only through `Deck`; `Deck.peek` moves the view without the projector; GUI-free modules stay importable without PyGObject so they can be unit-tested; `latex` runs with `-no-shell-escape` and paranoid file access, with a timeout, and one bad formula never hides the others; state and cache files are written atomically or content-addressed.

Environment: PyGObject comes from the system, so the venv is created with `--system-site-packages`; `ty` ignores unresolved imports only in the GTK modules, and Ruff ignores E402 there because `gi.require_version` must run first.

Extra gate: none beyond the common gate. Window behavior needs a manual run on a real two-monitor setup.

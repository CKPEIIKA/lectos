# LECTOS(1)

## NAME

`lectos` — Linux presenter console and projector for PDF slides and lecture notes

## SYNOPSIS

```text
lectos [OPTIONS] [PDF|FOLDER] [NOTES.md|NOTES.tex]
lectos-tui [OPTIONS] PDF|FOLDER [NOTES.md|NOTES.tex]
```

## DESCRIPTION

`lectos` presents a compiled PDF with optional Markdown or Beamer notes. Choose GTK or terminal for the console and GTK,
Zathura, or no projector independently. The GTK console adds slide previews, notes, search, overview, a timer, drawing,
and presentation recovery. Lectos reads Beamer notes but never compiles slides or edits the `.tex` file.

By default, `lectos` without arguments opens a chooser for slides, notes, or a folder. Drop a PDF, notes file, both files,
or a folder onto it. In the GTK console, `Ctrl+O` opens the slide chooser or switches presentations. Notes beside a PDF
are found automatically.

![The wide layout on a big screen: slide with ink and laser, audience and next previews, notes with typeset math, and the filmstrip](docs/screenshots/wide.png)

This project is vibe-coded. Treat the documented support boundaries and quality gates as the source of truth, and
verify behavior for your use case.

## INSTALLATION

Requires Python 3.13+, GTK 4, libadwaita 1.4+, PyGObject, and the Poppler GObject typelib. Optional tools are
`latex` and `dvipng` for formula images, `zathura` for the alternative projector, and `pdftoppm`, `pdftotext`, and
`chafa` for terminal previews.

Install from GitHub with `pipx`:

```bash
pipx install --python python3.13 --system-site-packages "lectos @ git+https://github.com/CKPEIIKA/lectos.git"
```

PyGObject and Poppler come from the system, so keep `--system-site-packages` enabled. For a source checkout, install
`uv` and run:

```bash
git clone https://github.com/CKPEIIKA/lectos.git
cd lectos
uv venv --system-site-packages --python /usr/bin/python3.13
uv sync --locked
```

## EXAMPLES

```bash
lectos                                  # choose slides and notes
lectos slides.pdf                      # use notes next to the PDF, if present
lectos slides.pdf notes.md             # name the notes explicitly
lectos talk/                           # choose slides and notes from a folder
lectos-tui slides.pdf notes.tex        # terminal console with Zathura
```

With a source checkout, run these commands with `uv run` (for example, `uv run lectos examples/slides.pdf`).

## KEYS

| Key | Action |
|---|---|
| `Ctrl+O` (GTK) | Choose slides or switch presentations |
| Arrows, Space, Page Up/Down, Home/End | Navigate slides |
| `:` | Open the command line; Tab completes and `:help` lists commands |
| `o`, `/` | Overview, search |
| `z`, `b`, `B` | Freeze, blackout, chalkboard |
| `d`, `e`, `p`, `s` | Mouse drawing, eraser, laser, drawing layout |
| `E`, `S`, `t`, `f`, `F` | Edit notes, settings, timer, projector fullscreen, console fullscreen |

Vim keys are on by default in GTK and always on in the terminal. Feature support depends on the selected console and
projector. With two monitors, the GTK projector opens fullscreen on the last one; with one, it stays windowed.

## FILES

- `$XDG_CONFIG_HOME/lectos/options.toml` — interface, layout, drawing, and projector options.
- `$XDG_STATE_HOME/lectos/` — presentation recovery, ink, and edits to Beamer notes; the `.tex` source stays untouched.
- `examples/` — sample slides, notes, and configuration.

## SEE ALSO

- [User guide](docs/usage.md) — layouts, notes, drawing, configuration, and screenshots.
- [lectos(1)](man/lectos.1), [lectos-tui(1)](man/lectos-tui.1) — command-line reference; read locally with `man -l man/lectos.1`.
- [TODO](docs/TODO.md), [DONE](docs/DONE.md) — backlog and completion history.

## DEVELOPMENT

```bash
uv sync --group dev
./scripts/quality.sh
```

GTK tests need a display.

## CREDITS

lectos was inspired by [pympress](https://github.com/Cimbali/pympress), by Cimbali and contributors. Its presenter
console, current and next slide previews, notes, timer, clickable PDF links, and Beamer notes pages drew on ideas from
pympress. lectos shares no code with it.

## LICENSE

GPL-3.0-only; see [LICENSE](LICENSE).

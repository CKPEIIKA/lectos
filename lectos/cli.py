"""Command-line entry points: ``lectos`` (GTK console by default) and ``lectos-tui`` (terminal console)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from lectos import i18n
from lectos.config import ConfigError, Options, load
from lectos.model import layout as layouts
from lectos.paths import discover, notes_for

CONSOLE_CHOICES = ("gtk", "tui")
PROJECTOR_CHOICES = ("gtk", "zathura", "none")
GTK_MISSING = "GTK 4 with PyGObject and the Poppler typelib is needed for this combination (see README)"


def build_parser(prog: str) -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Presenter console and projector for PDF slides with Markdown/LaTeX lecture notes.",
    )
    parser.add_argument("--version", action="version", version=version("lectos"))
    parser.add_argument(
        "pdf",
        type=Path,
        nargs="?",
        help="Compiled slides (PDF), or a folder with slides and notes. Omit to choose in a window.",
    )
    parser.add_argument(
        "notes",
        type=Path,
        nargs="?",
        help="Lecture notes: Markdown, or a Beamer .tex file (its \\note{} commands). Default: next to the slides.",
    )
    parser.add_argument(
        "--console", choices=CONSOLE_CHOICES, help="Presenter interface (default: gtk, or [ui] console)."
    )
    parser.add_argument(
        "--projector",
        choices=PROJECTOR_CHOICES,
        help="Audience window (default: gtk, or [ui] projector; tui: zathura).",
    )
    parser.add_argument(
        "--layout",
        choices=("auto", "compact", "wide", "draw"),
        help="GTK console layout (default: auto, by window width).",
    )
    parser.add_argument(
        "--lang", choices=("auto", "en", "ru", "de"), help="Interface language (default: from the environment)."
    )
    parser.add_argument(
        "--notes-pages",
        choices=layouts.NOTES_PAGES,
        help="Where Beamer's second-screen notes sit on each PDF page (default: auto, from the page shape).",
    )
    parser.add_argument("--windowed", action="store_true", help="Keep the GTK projector window windowed.")
    parser.add_argument("--monitor", type=int, help="GTK projector monitor index (default: last when several).")
    parser.add_argument("--fullscreen", action="store_true", help="Start the projector fullscreen.")
    parser.add_argument("--no-vim", action="store_true", help="Start with vim keys off (GTK console).")
    parser.add_argument("--config", type=Path, help="Options file (default: $XDG_CONFIG_HOME/lectos/options.toml).")
    return parser


def _resolve_inputs(args: argparse.Namespace) -> str:
    """Fill in the slides and notes from a folder or from next to the slides; returns an error text or ''."""
    if args.pdf is not None and args.pdf.is_dir():
        found = discover(args.pdf)
        if found is None:
            return f"no PDF in {args.pdf}"
        args.pdf, found_notes = found
        args.notes = args.notes or found_notes
    elif args.pdf is not None and args.notes is None:
        args.notes = notes_for(args.pdf)  # slides.tex or slides.md next to slides.pdf
    missing = next((p for p in (args.pdf, args.notes) if p is not None and not p.is_file()), None)
    return f"not a file: {missing}" if missing is not None else ""


def main(argv: Sequence[str] | None = None, *, default_console: str = "gtk", default_projector: str = "gtk") -> int:
    """Run the chosen console with the chosen projector."""
    args = build_parser("lectos" if default_console == "gtk" else "lectos-tui").parse_args(argv)
    failure = _resolve_inputs(args)
    if failure:
        print(f"lectos: {failure}", file=sys.stderr)
        return 2
    try:
        options = load(args.config)
    except ConfigError as exc:
        print(f"lectos: {exc}", file=sys.stderr)
        return 2
    if args.no_vim:
        options = replace(options, vim=False)
    if args.layout:
        options = replace(options, layout=args.layout)
    if args.notes_pages:
        options = replace(options, notes_pages=args.notes_pages)
    i18n.init(args.lang or options.language)
    console = args.console or options.console or default_console
    projector = args.projector or options.projector or default_projector
    try:
        return _dispatch(console, projector, args, options)
    except (ImportError, ValueError) as exc:
        print(f"lectos: {GTK_MISSING}: {exc}", file=sys.stderr)
        return 1


def main_tui(argv: Sequence[str] | None = None) -> int:
    """``lectos-tui``: terminal console, Zathura projector unless told otherwise (no GTK needed)."""
    return main(argv, default_console="tui", default_projector="zathura")


def _dispatch(console: str, projector: str, args: argparse.Namespace, options: Options) -> int:
    from lectos.notes.beamer import open_notes

    source = open_notes(args.notes, args.pdf) if args.notes and args.pdf else None
    if console == "gtk":
        from lectos.gtk.app import run  # imports GTK only when actually presenting

        return run(args.pdf, source, options, projector=projector, windowed=args.windowed, monitor=args.monitor)
    if args.pdf is None:
        print("lectos: the terminal console needs the slides (a PDF or a folder)", file=sys.stderr)
        return 2
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("lectos: the terminal console needs an interactive terminal", file=sys.stderr)
        return 2
    if projector == "gtk":
        from lectos.gtk.tuiglib import run as run_with_gtk_projector

        return run_with_gtk_projector(
            args.pdf, args.notes, options, windowed=args.windowed, monitor=args.monitor, fullscreen=args.fullscreen
        )
    return _run_terminal(projector, args, options)


def _run_terminal(projector: str, args: argparse.Namespace, options: Options) -> int:
    from lectos.projectors.projection import NullProjector
    from lectos.projectors.zathura import ProjectorError, Zathura
    from lectos.term.pdftools import PdfToolError
    from lectos.term.tui import make_tui, run_select

    zathura = Zathura(args.pdf.resolve()) if projector == "zathura" else None
    try:
        if zathura is not None:
            zathura.start()
        tui = make_tui(args.pdf, args.notes, options, zathura or NullProjector())
        if args.fullscreen:
            tui.execute("fullscreen on")
        run_select(tui, args.pdf)
    except (ProjectorError, PdfToolError) as exc:
        print(f"lectos: {exc}", file=sys.stderr)
        return 1
    finally:
        if zathura is not None:
            zathura.stop()
    return 0

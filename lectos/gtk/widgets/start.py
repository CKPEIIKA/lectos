"""The window shown when lectos starts without slides: choose slides, notes or a folder."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from lectos import state
from lectos.i18n import tr
from lectos.paths import NOTES_SUFFIXES, discover, notes_for

SLIDES_ICON = "lectos"
ICON_PX = 96
CONTENT_MAX_PX = 480
CONTENT_FIT_PX = 720  # tall enough that the default window shows everything without scrolling
MAX_DROP_FILES = 2


class StartWindow(Adw.ApplicationWindow):
    """Pick the PDF slides and optional notes (or one folder holding both), then start presenting."""

    def __init__(
        self,
        app: Gtk.Application,
        on_start: Callable[[Path, Path | None], None],
        notes_names: Sequence[str] = (),
    ) -> None:
        super().__init__(
            application=app, title=tr("lectos - open a presentation"), default_width=520, default_height=CONTENT_FIT_PX
        )
        self.on_start = on_start
        self.notes_names = notes_names
        self.slides: Path | None = None
        self.notes: Path | None = None
        self.slides_row = Adw.ActionRow(title=tr("Slides"), subtitle=tr("not chosen"))
        self.notes_row = Adw.ActionRow(title=tr("Notes"), subtitle=tr("none (optional)"))
        for row, handler, label in (
            (self.slides_row, self.choose_slides, tr("Choose…")),
            (self.notes_row, self.choose_notes, tr("Choose…")),
        ):
            button = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda _b, h=handler: h())
            row.add_suffix(button)
        group = Adw.PreferencesGroup()
        group.add(self.slides_row)
        group.add(self.notes_row)
        folder = Gtk.Button(label=tr("Open a folder…"), halign=Gtk.Align.CENTER, css_classes=["pill"])
        folder.connect("clicked", lambda _b: self.choose_folder())
        self.start_button = Gtk.Button(
            label=tr("Start"), halign=Gtk.Align.CENTER, sensitive=False, css_classes=["suggested-action", "pill"]
        )
        self.start_button.connect("clicked", lambda _b: self.start())
        description = tr(
            "Choose the PDF slides and, if you have them, the lecture notes (Markdown or Beamer .tex). "
            "You can also drop a PDF, notes file, or folder here, or press Ctrl+O to choose slides."
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=24)
        box.append(Gtk.Image(icon_name=SLIDES_ICON, pixel_size=ICON_PX, margin_bottom=6))
        box.append(Gtk.Label(label=tr("Open a presentation"), css_classes=["title-1"], wrap=True))
        box.append(Gtk.Label(label=description, wrap=True, justify=Gtk.Justification.CENTER, margin_bottom=12))
        for widget in (group, folder, self.start_button):
            box.append(widget)
        # A scrolled clamp, so the window can be smaller than the content (then it scrolls) and is never forced larger.
        page = Gtk.ScrolledWindow(
            child=Adw.Clamp(child=box, maximum_size=CONTENT_MAX_PX, margin_start=16, margin_end=16),
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_height=False,
        )
        toolbar = Adw.ToolbarView(content=page)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._drop_files)
        self.add_controller(drop)
        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", lambda *_args: self.choose_slides())
        self.add_action(open_action)

    # ---- choices ----
    def set_slides(self, pdf: Path) -> None:
        """Take the slides; notes next to them are found unless some were chosen."""
        self.slides = pdf
        self.slides_row.set_subtitle(str(pdf))
        if self.notes is None:
            self._show_notes(notes_for(pdf, self.notes_names), found=True)
        self.start_button.set_sensitive(True)

    def set_notes(self, notes: Path | None) -> None:
        """Take the notes, or none."""
        self._show_notes(notes, found=False)

    def _show_notes(self, notes: Path | None, *, found: bool) -> None:
        self.notes = notes
        if notes is None:
            self.notes_row.set_subtitle(tr("none (optional)"))
        else:
            self.notes_row.set_subtitle(str(notes) + (tr("  (found next to the slides)") if found else ""))

    def set_folder(self, folder: Path) -> bool:
        """Take the slides and notes found in a folder; False when it holds no PDF.

        Some file dialogs hand back a PDF chosen in the folder dialog: that is taken as the slides.
        """
        if folder.is_file() and folder.suffix.lower() == ".pdf":
            self.notes = None
            self.set_slides(folder)
            return True
        found = discover(folder, self.notes_names)
        if found is None:
            self.slides_row.set_subtitle(tr("no PDF in {folder}").format(folder=folder))
            return False
        self.notes = None
        self.set_slides(found[0])
        self._show_notes(found[1], found=True)
        return True

    def start(self) -> None:
        """Present the chosen slides."""
        if self.slides is not None:
            self.on_start(self.slides, self.notes)

    @staticmethod
    def _drop_paths(value: object) -> list[Path] | None:
        """Get a bounded list of local paths from a file drop."""
        if not isinstance(value, Gdk.FileList):
            return None
        files = value.get_files()
        if not files or len(files) > MAX_DROP_FILES:
            return None
        paths: list[Path] = []
        for file in files:
            path = file.get_path()
            if path is None:
                return None
            paths.append(Path(path))
        return paths

    def _apply_drop(self, paths: list[Path]) -> bool:
        """Accept one PDF, one notes file, both together, or one folder containing a presentation."""
        if not paths:
            return False
        if len(paths) == 1 and paths[0].is_dir():
            return self.set_folder(paths[0])
        slides = [path for path in paths if path.is_file() and path.suffix.lower() == ".pdf"]
        notes = [path for path in paths if path.is_file() and path.suffix.lower() in NOTES_SUFFIXES]
        if len(slides) > 1 or len(notes) > 1 or len(slides) + len(notes) != len(paths):
            return False
        if slides:
            self.set_slides(slides[0])
        if notes:
            self.set_notes(notes[0])
        return bool(slides or notes)

    def _drop_files(self, _target: Gtk.DropTarget, value: object, _x: float, _y: float) -> bool:
        """Route local file drops into the same selection methods as the file dialogs."""
        paths = self._drop_paths(value)
        return self._apply_drop(paths) if paths is not None else False

    # ---- file dialogs ----
    def _start_folder(self) -> Path | None:
        """Where the file chooser opens: next to what is chosen already, else where it last picked something."""
        chosen = self.slides or self.notes
        return chosen.parent if chosen is not None else state.last_folder()

    def _dialog(self, title: str, patterns: tuple[str, ...] = ()) -> Gtk.FileDialog:
        dialog = Gtk.FileDialog(title=title)
        folder = self._start_folder()
        if folder is not None:
            dialog.set_initial_folder(Gio.File.new_for_path(str(folder)))
        if patterns:
            files = Gtk.FileFilter(name=", ".join(patterns))
            for pattern in patterns:
                files.add_pattern(pattern)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(files)
            dialog.set_filters(filters)
        return dialog

    def choose_slides(self) -> None:
        """Ask for the PDF."""
        self._dialog(tr("Choose the slides"), ("*.pdf",)).open(self, None, self._picked, self.set_slides)

    def choose_notes(self) -> None:
        """Ask for the notes file."""
        self._dialog(tr("Choose the notes"), ("*.md", "*.tex")).open(self, None, self._picked, self.set_notes)

    def choose_folder(self) -> None:
        """Ask for a folder with slides and notes."""
        self._dialog(tr("Choose a folder")).select_folder(self, None, self._picked, self.set_folder)

    def _picked(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, apply: Callable[[Path], object]) -> None:
        finish = dialog.select_folder_finish if apply == self.set_folder else dialog.open_finish
        try:
            file = finish(result)
        except GLib.Error:
            return  # cancelled
        path = file.get_path()
        if path is not None:
            picked = Path(path)
            state.remember_folder(picked if apply == self.set_folder else picked.parent)
            apply(picked)

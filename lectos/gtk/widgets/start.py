"""The window shown when lectos starts without slides: choose slides, notes or a folder."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from lectos.i18n import tr
from lectos.paths import discover, notes_for

SLIDES_ICON = "lectos"


class StartWindow(Adw.ApplicationWindow):
    """Pick the PDF slides and optional notes (or one folder holding both), then start presenting."""

    def __init__(self, app: Gtk.Application, on_start: Callable[[Path, Path | None], None]) -> None:
        super().__init__(
            application=app, title=tr("lectos - open a presentation"), default_width=520, default_height=560
        )
        self.on_start = on_start
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
        page = Adw.StatusPage(
            icon_name=SLIDES_ICON,
            title=tr("Open a presentation"),
            description=tr("Choose the PDF slides and, if you have them, the lecture notes (Markdown or Beamer .tex)."),
        )
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=16, margin_end=16, margin_bottom=16
        )
        for widget in (group, folder, self.start_button):
            box.append(widget)
        page.set_child(box)
        toolbar = Adw.ToolbarView(content=page)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar)

    # ---- choices ----
    def set_slides(self, pdf: Path) -> None:
        """Take the slides; notes next to them are found unless some were chosen."""
        self.slides = pdf
        self.slides_row.set_subtitle(str(pdf))
        if self.notes is None:
            self._show_notes(notes_for(pdf), found=True)
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
        found = discover(folder)
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

    # ---- file dialogs ----
    def _dialog(self, title: str, patterns: tuple[str, ...] = ()) -> Gtk.FileDialog:
        dialog = Gtk.FileDialog(title=title)
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
            apply(Path(path))

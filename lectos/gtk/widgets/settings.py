"""Settings window: what the console shows, the layout and a few behaviours. Every change is a console command."""

from __future__ import annotations

from typing import Protocol

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from lectos.i18n import noop, tr
from lectos.model import layout as layouts
from lectos.model.ink import COLORS

PANEL_TITLES = {
    "notes": noop("Lecture notes"),
    "audience": noop("Audience preview"),
    "next": noop("Next slide preview"),
    "strip": noop("Filmstrip (wide layout)"),
    "status": noop("Status bar"),
    "palette": noop("Pen palette"),
}
LAYOUT_TITLES = (
    (layouts.AUTO, noop("Automatic")),
    (layouts.COMPACT, noop("Compact")),
    (layouts.WIDE, noop("Wide")),
    (layouts.DRAW, noop("Drawing")),
)
MAX_TARGET_MIN = 24 * 60
BEHAVIOURS = (  # (command, host attribute, title, subtitle)
    ("vim", "vim_on", noop("Vim keys"), noop("h j k l, :, / and friends (change keys: :bind, [keys] in options.toml)")),
    (
        "show-slide", "show_slide_on", noop("Show the slide for note hits"),
        noop("a search hit in the notes also previews its slide"),
    ),
    (
        "slide-times", "slide_times_on", noop("Time per slide"),
        noop("shown in the overview, counted while the timer runs"),
    ),
    ("menubar", "menubar_on", noop("Menu bar"), noop("File ... Help; pressing Alt does the same")),
)  # fmt: skip
MIN_ZOOM, MAX_ZOOM = 1.2, 8.0


class SettingsHost(Protocol):
    """What the window reads from, and sends to, the console."""

    hidden: set[str]
    layout_mode: str
    previous: int
    upcoming: int
    vim_on: bool
    show_slide_on: bool
    slide_times_on: bool
    menubar_on: bool
    palette: tuple[str, ...]
    notes_names: tuple[str, ...]
    zoom_factor: float

    def execute(self, line: str) -> None:
        """Run a command line."""

    def target_minutes(self) -> int:
        """The planned lecture length."""


class SettingsWindow(Adw.Window):
    """Rows are derived from the console's real state by ``sync`` and change it only through commands."""

    def __init__(self, host: SettingsHost, parent: Gtk.Window) -> None:
        super().__init__(title=tr("Settings"), transient_for=parent, modal=True, default_width=460, default_height=640)
        self.host = host
        self._syncing = False
        self._notes_shown = ""
        self.panel_rows = {name: self._switch(tr(title), "", f"panel {name}") for name, title in PANEL_TITLES.items()}
        self.layout_row = Adw.ComboRow(title=tr("Layout"), model=Gtk.StringList.new([tr(t) for _, t in LAYOUT_TITLES]))
        self.layout_row.connect("notify::selected", self._layout_chosen)
        self.previous_row = self._spin(tr("Slides before the current one"), 0, layouts.MAX_PREVIOUS, "previous")
        self.upcoming_row = self._spin(tr("Slides after the current one"), 0, layouts.MAX_UPCOMING, "upcoming")
        self.target_row = self._spin(tr("Lecture length (minutes)"), 1, MAX_TARGET_MIN, "target")
        self.behaviour_rows = {name: self._switch(tr(title), tr(sub), name) for name, _a, title, sub in BEHAVIOURS}
        self.zoom_row = Adw.SpinRow.new_with_range(MIN_ZOOM, MAX_ZOOM, 0.5)
        self.zoom_row.set_title(tr("Zoom factor"))
        self.zoom_row.set_digits(1)
        self.zoom_row.connect("notify::value", lambda r, _p: self._zoomed(r.get_value()))
        self.palette_rows = {c: Adw.SwitchRow(title=tr(c)) for c in COLORS}  # read together by ``_palette_chosen``
        for row in self.palette_rows.values():
            row.connect("notify::active", lambda _r, _p: self._palette_chosen())
        self.notes_row = Adw.EntryRow(title=tr("Notes file names (separated by spaces)"))
        self.notes_row.set_show_apply_button(True)
        self.notes_row.connect("apply", lambda r: self._notes_named(r.get_text()))
        page = Adw.PreferencesPage()
        for title, rows in (
            (tr("Show on screen"), self.panel_rows.values()),
            (tr("Layout"), (self.layout_row, self.previous_row, self.upcoming_row)),
            (tr("Behaviour"), (self.target_row, *self.behaviour_rows.values(), self.zoom_row)),
            (tr("Pen palette"), self.palette_rows.values()),
            (tr("Files"), (self.notes_row,)),
        ):
            group = Adw.PreferencesGroup(title=title)
            for row in rows:
                group.add(row)
            page.add(group)
        toolbar = Adw.ToolbarView(content=page)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar)
        self.sync()

    def _switch(self, title: str, subtitle: str, command: str) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle)
        row.connect("notify::active", lambda r, _p: self._toggled(command, r.get_active()))
        return row

    def _spin(self, title: str, low: int, high: int, command: str) -> Adw.SpinRow:
        row = Adw.SpinRow.new_with_range(low, high, 1)
        row.set_title(title)
        row.connect("notify::value", lambda r, _p: self._spun(command, round(r.get_value())))
        return row

    def _toggled(self, command: str, active: bool) -> None:
        if not self._syncing:
            self.host.execute(f"{command} {'on' if active else 'off'}")

    def _spun(self, command: str, value: int) -> None:
        if not self._syncing:
            self.host.execute(f"{command} {value}")

    def _zoomed(self, value: float) -> None:
        if not self._syncing:
            self.host.execute(f"zoom-factor {value:.1f}")

    def _palette_chosen(self) -> None:
        names = [c for c, row in self.palette_rows.items() if row.get_active()]
        if not self._syncing and names:
            self.host.execute("palette " + " ".join(names))
        elif not self._syncing:
            self.sync()  # at least one colour must stay

    def _notes_named(self, text: str) -> None:
        self.host.execute(f"notes-names {text.strip() or 'none'}")  # "apply" only comes from the user

    def _layout_chosen(self, row: Adw.ComboRow, _param: object) -> None:
        if not self._syncing:
            self.host.execute(f"layout {LAYOUT_TITLES[row.get_selected()][0]}")

    def sync(self) -> None:
        """Show the console's real state."""
        host = self.host
        self._syncing = True
        try:
            for name, row in self.panel_rows.items():
                row.set_active(name not in host.hidden)
            self.layout_row.set_selected([m for m, _ in LAYOUT_TITLES].index(host.layout_mode))
            self.previous_row.set_value(host.previous)
            self.upcoming_row.set_value(host.upcoming)
            self.target_row.set_value(host.target_minutes())
            for command, attribute, _title, _sub in BEHAVIOURS:
                self.behaviour_rows[command].set_active(getattr(host, attribute))
            self.zoom_row.set_value(host.zoom_factor)
            for color, row in self.palette_rows.items():
                row.set_active(color in host.palette)
            names = " ".join(host.notes_names)
            if names != self._notes_shown:  # unchanged: leave what is being typed alone
                self._notes_shown = names
                self.notes_row.set_text(names)
        finally:
            self._syncing = False

"""Settings window: what the console shows, the layout and a few behaviours. Every change is a console command."""

from __future__ import annotations

from typing import Protocol

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from lectos.i18n import noop, tr
from lectos.model import layout as layouts

PANEL_TITLES = {
    "notes": noop("Lecture notes"),
    "audience": noop("Audience preview"),
    "next": noop("Next slide preview"),
    "strip": noop("Filmstrip (wide layout)"),
    "status": noop("Status bar"),
}
LAYOUT_TITLES = (
    (layouts.AUTO, noop("Automatic")),
    (layouts.COMPACT, noop("Compact")),
    (layouts.WIDE, noop("Wide")),
    (layouts.DRAW, noop("Drawing")),
)
MAX_TARGET_MIN = 24 * 60
BEHAVIOURS = (  # (command, title, subtitle)
    ("vim", noop("Vim keys"), noop("h j k l, :, / and friends")),
    ("show-slide", noop("Show the slide for note hits"), noop("a search hit in the notes also previews its slide")),
)


class SettingsHost(Protocol):
    """What the window reads from, and sends to, the console."""

    hidden: set[str]
    layout_mode: str
    previous: int
    upcoming: int
    vim_on: bool
    show_slide_on: bool

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
        self.panel_rows = {name: self._switch(tr(title), "", f"panel {name}") for name, title in PANEL_TITLES.items()}
        self.layout_row = Adw.ComboRow(title=tr("Layout"), model=Gtk.StringList.new([tr(t) for _, t in LAYOUT_TITLES]))
        self.layout_row.connect("notify::selected", self._layout_chosen)
        self.previous_row = self._spin(tr("Slides before the current one"), 0, layouts.MAX_PREVIOUS, "previous")
        self.upcoming_row = self._spin(tr("Slides after the current one"), 0, layouts.MAX_UPCOMING, "upcoming")
        self.target_row = self._spin(tr("Lecture length (minutes)"), 1, MAX_TARGET_MIN, "target")
        self.behaviour_rows = {name: self._switch(tr(title), tr(sub), name) for name, title, sub in BEHAVIOURS}
        page = Adw.PreferencesPage()
        for title, rows in (
            (tr("Show on screen"), self.panel_rows.values()),
            (tr("Layout"), (self.layout_row, self.previous_row, self.upcoming_row)),
            (tr("Behaviour"), (self.target_row, *self.behaviour_rows.values())),
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
            self.behaviour_rows["vim"].set_active(host.vim_on)
            self.behaviour_rows["show-slide"].set_active(host.show_slide_on)
        finally:
            self._syncing = False

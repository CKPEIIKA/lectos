"""Presenter console: preview, notes with math, timer, overview, search, vim keys."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from lectos import commands, mathimg, notes, search
from lectos import header as header_items
from lectos import layout as layouts
from lectos.config import Header, Options
from lectos.deck import Timer, format_seconds, parse_minutes, schedule_summary
from lectos.i18n import noop, tr
from lectos.ink import COLORS
from lectos.inkinput import InkInput
from lectos.keys import Vim, key_for
from lectos.notes import NotesError, NotesSource, Section
from lectos.paths import unique
from lectos.pdfdoc import PdfDoc
from lectos.projection import COMMAND_CAPS, Projector, apply_caps
from lectos.stage import Stage
from lectos.toolcmds import TOOL_FLAG_MESSAGES, Tools

SCROLL_STEP = 60.0
THUMB_W, THUMB_H = 200, 125
SMALL_H = 130
WIDE_ROW_H = 220
WIDE_SLIDE_SHARE = 0.58
PANE_TOLERANCE_PX = 8
TOAST_S = 3
RESIZE_DEBOUNCE_MS = 120
TOGGLE_CSS = {  # header toggles that light up while active
    "freeze": "suggested-action", "blackout": "destructive-action", "board": "suggested-action",
    "laser": "suggested-action", "draw": "suggested-action", "eraser": "suggested-action",
}  # fmt: skip
BANNERS = (  # (state, style class, title, button, command that turns it off); title and button are translated
    (
        "freeze",
        "warning",
        noop("Projector frozen on slide {page}: the audience does not see what you view"),
        noop("Unfreeze"),
        "freeze off",
    ),
    ("blackout", "error", noop("Projector is blacked out"), noop("Restore"), "blackout off"),
    ("board", "accent", noop("The audience sees the chalkboard"), noop("Back to slides"), "board off"),
)
COLOR_WORDS = (noop("red"), noop("yellow"), noop("green"), noop("blue"), noop("white"), noop("black"))  # for tr()
BOARD_WORDS = (noop("chalk"), noop("ruled"), noop("grid"))  # board style names, shown through tr()
SEARCH_PANEL_H = 260


def _numbers(template: str, *values: int) -> tuple[tuple[str, str], ...]:
    """Choices whose label is ``template`` with ``{n}`` replaced by the value when shown."""
    return tuple((template, str(v)) for v in values)


COLOR_CHOICES = (
    (noop("Red"), "red"), (noop("Yellow"), "yellow"), (noop("Green"), "green"),
    (noop("Blue"), "blue"), (noop("White"), "white"), (noop("Black"), "black"),
)  # fmt: skip
RADIO_MENUS = {  # action -> (submenu title, ((label, value), ...)); titles and labels are translated when shown
    "target": (noop("Lecture length"), _numbers(noop("{n} minutes"), 30, 45, 60, 90, 120)),
    "color": (noop("Pen colour"), COLOR_CHOICES),
    "width": (noop("Pen width"), _numbers(noop("{n} px"), 2, 4, 8, 12, 20)),
    "smooth": (
        noop("Smoothing"),
        ((noop("Off"), "0"), (noop("Low"), "1"), (noop("Medium"), "3"), (noop("High"), "5")),
    ),
    "eraser-size": (
        noop("Eraser size"),
        ((noop("Small"), "8"), (noop("Medium"), "14"), (noop("Large"), "30"), (noop("Huge"), "60")),
    ),
    "board-style": (
        noop("Chalkboard background"),
        (
            (noop("Chalk"), "chalk"), (noop("Black"), "black"), (noop("White"), "white"),
            (noop("Ruled"), "ruled"), (noop("Grid"), "grid"),
        ),
    ),
    "laser-color": (noop("Colour"), COLOR_CHOICES[:5]),
    "laser-size": (noop("Size"), _numbers(noop("{n} px"), 5, 9, 14, 22)),
    "laser-style": (noop("Shape"), ((noop("Dot"), "dot"), (noop("Ring"), "ring"), (noop("Cross"), "cross"))),
    "layout": (
        noop("Layout"),
        ((noop("Automatic"), "auto"), (noop("Compact"), "compact"), (noop("Wide"), "wide")),
    ),
    "upcoming": (noop("Upcoming slides"), _numbers(noop("{n}"), 4, 8, 12, 16)),
}  # fmt: skip

ACCENT_RGB = (0.27, 0.53, 1.0)
LIVE_RGB = (0.9, 0.15, 0.15)
TICK_MS = 500
HEADING_SCALE = {"h1": 1.6, "h2": 1.35, "h3": 1.15}
TAGS = {
    "bold": {"weight": Pango.Weight.BOLD},
    "italic": {"style": Pango.Style.ITALIC},
    "code": {"family": "monospace"},
    "raw": {"family": "monospace", "foreground": "#a33"},
    "hit": {"background": "#ffee0066"},
    "current": {"paragraph_background": "#4488ff22"},
}


class ConsoleWindow(Adw.ApplicationWindow):
    """The presenter's window. Owns the timer, notes view, and the keyboard."""

    def __init__(
        self,
        app: Gtk.Application,
        stage: Stage,
        *,
        doc: PdfDoc,
        projector: Projector,
        notes: NotesSource | None,
        options: Options,
    ) -> None:
        super().__init__(application=app, title="lectos", default_width=940, default_height=800)
        self.stage, self.doc, self.deck, self.ink = stage, doc, stage.deck, stage.ink
        self.projector, self.notes = projector, notes
        self.tools = Tools(self.ink, self.deck, stage.laser)
        self.timer = Timer(target_min=options.target_min)
        self.vim = Vim()
        self.vim_on = options.vim
        self.show_slide_on = True
        self.layout_mode = options.layout
        self.layout_active = layouts.COMPACT
        self.previous, self.upcoming = options.previous, options.upcoming
        self.hits: list[search.Hit] = []
        self.hit = -1
        self.dirty = False
        self.last_message = ""
        self._init_widget_state()
        self._commands = self._build_commands()
        self._build(options)
        self.deck.subscribe(self._on_deck)
        self.ink.subscribe(self._on_ink)
        GLib.timeout_add(TICK_MS, self._tick)
        self.poll_notes()
        self._on_deck()

    def _init_widget_state(self) -> None:
        """Bookkeeping for widgets and caches that are filled in while the window is built."""
        self._toast: Adw.Toast | None = None
        self._banners: dict[str, Adw.Banner] = {}
        self._help_page: Gtk.Widget | None = None
        self._resize_pending = False
        self._overview_origin: int | None = None
        self._overview_busy = False
        self._pane: dict[str, int] = {}
        self._sections: list[Section] = []
        self._textures: dict[mathimg.Formula, Gdk.Texture] = {}
        self._notes_mtime = -1
        self._stage_areas: list[Gtk.DrawingArea] = []
        self._plain_areas: list[Gtk.DrawingArea] = []
        self._strip_box: Gtk.Box | None = None
        self._toggles: dict[str, Gtk.ToggleButton] = {}
        self._flag_actions: dict[str, Gio.SimpleAction] = {}
        self._radio_actions: dict[str, Gio.SimpleAction] = {}
        self._syncing = False
        self._fitting = False
        self.scroller: Gtk.ScrolledWindow | None = None

    # ---- construction ----
    def _build(self, options: Options) -> None:
        self.buffer = Gtk.TextBuffer()
        for name, props in TAGS.items():
            self.buffer.create_tag(name, **props)
        for name, scale in HEADING_SCALE.items():
            self.buffer.create_tag(name, scale=scale, weight=Pango.Weight.BOLD)
        self.main_holder = Gtk.Box(vexpand=True)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.main_holder, "main")
        self.stack.add_named(self._build_overview(), "overview")
        self._install_actions()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self._build_banners())
        content.append(self._build_search())  # a panel above the slides: searching never hides them
        content.append(self.stack)
        self.toasts = Adw.ToastOverlay(child=content)
        toolbar = Adw.ToolbarView(content=self.toasts)
        toolbar.add_top_bar(self._build_header(options.header))
        toolbar.add_bottom_bar(self._build_footer())
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        for prop in ("default-width", "fullscreened", "maximized"):
            self.connect(f"notify::{prop}", self._on_resized)
        self._apply_layout(force=True)

    def _on_resized(self, *_args: object) -> None:
        """Window size changed: after it settles, pick the layout and realign what depends on the width."""
        if not self._resize_pending:
            self._resize_pending = True
            GLib.timeout_add(RESIZE_DEBOUNCE_MS, self._after_resize)

    def _after_resize(self) -> bool:
        self._resize_pending = False
        self._apply_layout()
        self._fit_pane()
        self._refresh_strip()
        if self.scroller is not None:
            self._after_layout(self.scroller.get_vadjustment().get_value())
        return False

    # ---- state you can see: banners, toasts, tool summary ----
    def _build_banners(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for name, css, _title, button, command in BANNERS:
            banner = Adw.Banner(button_label=tr(button), revealed=False)
            banner.add_css_class(css)
            banner.connect("button-clicked", lambda _b, cmd=command: self.execute(cmd))
            self._banners[name] = banner
            box.append(banner)
        return box

    def _sync_banners(self) -> None:
        for name, _css, title, _button, _cmd in BANNERS:
            banner = self._banners[name]
            banner.set_title(tr(title).format(page=self.deck.page + 1))
            banner.set_revealed(self._flag(name))

    def _color_name(self, color: str) -> str:
        return next((name for name, value in COLORS.items() if value == color), color)

    def _tool_summary(self) -> str:
        if "ink" not in self.projector.caps:
            return ""
        tool, deck = self.ink.tool, self.deck
        kind = tr("highlighter") if tool.highlighter else tr("pen")
        parts = [f"{kind} {tr(self._color_name(tool.color))} {int(tool.width)}"]
        for text, on in (
            (tr("eraser"), tool.eraser),
            (tr("mouse draws"), tool.mouse_draw),
            (tr("laser"), deck.laser_on),
        ):
            if on:
                parts.append(text)
        if deck.board:
            parts.append(tr("board: {style}").format(style=tr(deck.board_style)))
        return ", ".join(parts)

    def _set_status(self, message: str, *, undo: bool = False) -> None:
        """Show a message as a toast (``undo`` adds an Undo button that restores erased ink)."""
        self.last_message = message
        if not message:
            return
        if self._toast is not None:
            self._toast.dismiss()
        toast = Adw.Toast(title=message, timeout=TOAST_S)
        if undo:
            toast.set_button_label(tr("Undo"))
            toast.set_action_name("win.restore-all")
        self._toast = toast
        self.toasts.add_toast(toast)

    # ---- header bar (configurable) ----
    def _icon_name(self, candidates: tuple[str, ...]) -> str | None:
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        return next((name for name in candidates if theme.has_icon(name)), None)

    def _item_button(self, name: str) -> Gtk.Button:
        item = header_items.ITEMS[name]
        icon = self._icon_name(item.icons)
        kwargs = {"icon_name": icon} if icon else {"label": item.label}
        if item.toggle:
            button: Gtk.Button = Gtk.ToggleButton(tooltip_text=tr(item.tip), css_classes=["flat"], **kwargs)
            button.connect("toggled", lambda b, n=name: self._toggled(n, b.get_active()))
            self._toggles[name] = button
        else:
            button = Gtk.Button(tooltip_text=tr(item.tip), css_classes=["flat"], **kwargs)
            button.connect("clicked", lambda _b, cmd=item.command: self.execute(cmd))
        cap = COMMAND_CAPS.get(item.command)
        if cap is not None and cap not in self.projector.caps:
            button.set_sensitive(False)
            button.set_tooltip_text(tr("{tip} - not supported by this projector").format(tip=tr(item.tip)))
        return button

    def _toggled(self, name: str, active: bool) -> None:
        if not self._syncing:
            self.execute(f"{header_items.ITEMS[name].command} {'on' if active else 'off'}")

    def _header_widget(self, name: str) -> Gtk.Widget:
        if name == "goto":
            self.goto_entry = Gtk.Entry(
                width_chars=3, max_width_chars=3, placeholder_text="#", tooltip_text=tr("go to slide number")
            )
            self.goto_entry.connect("activate", self._goto_entry)
            return self.goto_entry
        if name == "menu":
            return Gtk.MenuButton(
                icon_name="open-menu-symbolic", menu_model=self._menu_model(), tooltip_text=tr("Menu"), primary=True
            )
        return self._item_button(name)

    def _title_widget(self, kind: str) -> Gtk.Widget | None:
        self.timer_icon = Gtk.Image(icon_name="media-playback-start-symbolic")
        self.timer_label = Gtk.Label(label="0:00", css_classes=["monospace"])
        box = Gtk.Box(spacing=6)
        box.append(self.timer_icon)
        box.append(self.timer_label)
        self.timer_button = Gtk.Button(
            child=box, css_classes=["flat"], tooltip_text=tr("elapsed / time left; click to start or pause (t)")
        )
        self.timer_button.connect("clicked", lambda _b: self.execute("timer"))
        self.title_pos = Gtk.Label(css_classes=["monospace"], tooltip_text=tr("viewed slide / total"))
        return {"timer": self.timer_button, "slide": self.title_pos}.get(kind)

    def _build_header(self, cfg: Header) -> Gtk.HeaderBar:
        bar = Gtk.HeaderBar()
        for name in cfg.start:
            bar.pack_start(self._header_widget(name))
        title = self._title_widget(cfg.title)
        if title is not None:
            bar.set_title_widget(title)
        for name in reversed(cfg.end):  # pack_end stacks from the right edge inwards
            bar.pack_end(self._header_widget(name))
        return bar

    # ---- menu model and actions (GTK 4 style: Gio.Menu + Gio.SimpleAction) ----
    def _flag(self, name: str) -> bool:
        deck, tool = self.deck, self.ink.tool
        return {
            "freeze": deck.frozen, "blackout": deck.blackout, "board": deck.board, "laser": deck.laser_on,
            "draw": tool.mouse_draw, "eraser": tool.eraser, "highlighter": tool.highlighter,
            "projector-fullscreen": self.projector.is_fullscreen(), "fullscreen": self.is_fullscreen(),
            "vim": self.vim_on, "show-slide": self.show_slide_on,
        }[name]  # fmt: skip

    def _radio_value(self, name: str) -> str:
        tool, laser = self.ink.tool, self.stage.laser
        return {
            "layout": self.layout_mode, "upcoming": str(self.upcoming), "target": str(self.timer.target_min),
            "color": self._color_name(tool.color), "width": str(int(tool.width)), "smooth": str(tool.smoothing),
            "eraser-size": str(round(tool.eraser_radius)), "board-style": self.deck.board_style,
            "laser-color": self._color_name(laser.color), "laser-size": str(round(laser.size)),
            "laser-style": laser.style,
        }[name]  # fmt: skip

    def _install_actions(self) -> None:
        plain = (
            "timer", "timer-reset", "undo", "redo", "clear", "clear-all", "restore-all", "export",
            "overview", "search", "prev", "next", "help",
        )  # fmt: skip
        flags = (
            "freeze", "blackout", "board", "laser", "draw", "eraser", "highlighter",
            "projector-fullscreen", "fullscreen", "vim", "show-slide",
        )  # fmt: skip
        for name in plain:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cmd=name: self.execute(cmd))
            self.add_action(action)
        for name, prefill in (("goto-prompt", ":goto "), ("target-prompt", ":target ")):
            prompt = Gio.SimpleAction.new(name, None)
            prompt.connect("activate", lambda _a, _p, text=prefill: self._open_command(text))
            self.add_action(prompt)
        for name in flags:
            action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant.new_boolean(False))
            action.connect("activate", lambda _a, _p, n=name: self.execute(f"{n} {'off' if self._flag(n) else 'on'}"))
            self.add_action(action)
            self._flag_actions[name] = action
        for name in RADIO_MENUS:
            action = Gio.SimpleAction.new_stateful(
                name, GLib.VariantType.new("s"), GLib.Variant.new_string(self._radio_value(name))
            )
            action.connect("activate", lambda _a, p, n=name: self.execute(f"{n} {p.get_string()}"))
            self.add_action(action)
            self._radio_actions[name] = action
        for name, cap in COMMAND_CAPS.items():
            action = self.lookup_action(name)
            if action is not None and cap not in self.projector.caps:
                action.set_enabled(False)  # greyed out in the menu: this projector cannot do it

    def _sync_actions(self) -> None:
        """Bring menu marks, header toggles, banners and the tool summary in line with the real state."""
        self._syncing = True
        try:
            for name, action in self._flag_actions.items():
                action.set_state(GLib.Variant.new_boolean(self._flag(name)))
            for name, action in self._radio_actions.items():
                action.set_state(GLib.Variant.new_string(self._radio_value(name)))
            for name, button in self._toggles.items():
                active = self._flag(header_items.ITEMS[name].command)
                if button.get_active() != active:
                    button.set_active(active)
                css = TOGGLE_CSS.get(name)
                if css is not None:
                    (button.add_css_class if active else button.remove_css_class)(css)
        finally:
            self._syncing = False
        self._sync_banners()
        self.tools_label.set_label(self._tool_summary())

    @staticmethod
    def _menu_item(label: str, action: str, accel: str = "") -> Gio.MenuItem:
        item = Gio.MenuItem.new(label, f"win.{action}")
        if accel:
            item.set_attribute_value("accel", GLib.Variant.new_string(accel))  # display only: shown as a key hint
        return item

    def _menu_model(self) -> Gio.Menu:
        """The main menu: everyday actions inline, the rest grouped in submenus."""

        def section(*entries: Gio.MenuItem | tuple[str, Gio.Menu]) -> Gio.Menu:
            menu = Gio.Menu()
            for entry in entries:
                if isinstance(entry, tuple):
                    menu.append_submenu(*entry)
                else:
                    menu.append_item(entry)
            return menu

        def radios(action: str) -> tuple[str, Gio.Menu]:
            title, choices = RADIO_MENUS[action]
            items = (Gio.MenuItem.new(tr(label).format(n=value), f"win.{action}::{value}") for label, value in choices)
            return tr(title), section(*items)

        def inline(menu: Gio.Menu, *action_names: str) -> None:
            for action in action_names:  # radio choices shown directly under a heading
                title, choices = RADIO_MENUS[action]
                items = (
                    Gio.MenuItem.new(tr(label).format(n=value), f"win.{action}::{value}") for label, value in choices
                )
                menu.append_section(tr(title), section(*items))

        item = self._menu_item
        timer, drawing, laser = Gio.Menu(), Gio.Menu(), Gio.Menu()
        timer.append_section(None, section(
            item(tr("Start or pause"), "timer", "t"), item(tr("Reset"), "timer-reset"),
        ))  # fmt: skip
        timer.append_section(None, section(radios("target"), item(tr("Custom length…"), "target-prompt")))
        drawing.append_section(None, section(
            item(tr("Mouse drawing"), "draw", "d"), item(tr("Eraser"), "eraser", "e"),
            item(tr("Highlighter"), "highlighter"),
        ))  # fmt: skip
        drawing.append_section(None, section(radios("color"), radios("width"), radios("smooth"), radios("eraser-size")))
        drawing.append_section(None, section(
            item(tr("Undo"), "undo", "u"), item(tr("Redo"), "redo", "<Shift>u"), item(tr("Clear slide ink"), "clear"),
            item(tr("Erase all ink"), "clear-all"), item(tr("Restore erased ink"), "restore-all"),
        ))  # fmt: skip
        drawing.append_section(None, section(item(tr("Export annotated PDF"), "export")))
        laser.append_section(None, section(item(tr("Laser pointer"), "laser", "p")))
        inline(laser, "laser-color", "laser-size", "laser-style")

        menu = Gio.Menu()
        menu.append_section(None, section(
            item(tr("Previous slide"), "prev", "h"), item(tr("Next slide"), "next", "l"),
            item(tr("Go to slide…"), "goto-prompt", "colon"), item(tr("Overview"), "overview", "o"),
            item(tr("Search"), "search", "slash"),
        ))  # fmt: skip
        menu.append_section(tr("Audience"), section(
            item(tr("Freeze"), "freeze", "z"), item(tr("Blackout"), "blackout", "b"),
            item(tr("Chalkboard"), "board", "<Shift>b"), item(tr("Projector fullscreen"), "projector-fullscreen", "f"),
        ))  # fmt: skip
        menu.append_section(tr("Tools"), section(
            (tr("Timer"), timer), (tr("Drawing"), drawing), (tr("Laser pointer"), laser), radios("board-style"),
        ))  # fmt: skip
        menu.append_section(tr("View"), section(
            radios("layout"), radios("upcoming"), item(tr("Console fullscreen"), "fullscreen", "<Shift>f"),
        ))  # fmt: skip
        menu.append_section(None, section(
            item(tr("Vim keys"), "vim"), item(tr("Show slide for note hits"), "show-slide"),
            item(tr("Help and shortcuts"), "help", "question"),
        ))  # fmt: skip
        return menu

    def _build_footer(self) -> Gtk.Box:
        self.cmd = Gtk.Entry(visible=False, placeholder_text=tr(":command  (Tab, :help)"), width_chars=22)
        self.cmd.connect("activate", self._run_command)
        cmd_keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        cmd_keys.connect("key-pressed", self._cmd_key)
        self.cmd.add_controller(cmd_keys)
        self.tools_label = Gtk.Label(
            xalign=0, hexpand=True, margin_start=8, ellipsize=Pango.EllipsizeMode.END,
            css_classes=["dim-label", "caption"], tooltip_text=tr("current pen, eraser, laser and board"),
        )  # fmt: skip
        self.info = Gtk.Label(
            margin_end=8,
            css_classes=["dim-label", "monospace"],
            tooltip_text=tr("schedule against the planned length, estimated finish time, clock"),
        )
        self.pos = Gtk.Label(
            margin_start=8, css_classes=["monospace"], tooltip_text=tr("viewed slide / total (projected slide)")
        )
        footer = Gtk.Box(margin_top=2, margin_bottom=2)
        for w in (self.pos, self.cmd, self.tools_label, self.info):
            footer.append(w)
        return footer

    # ---- previews and layouts ----
    def _page_area(self, get_page, height: int | None = None, *, staged: bool = True) -> Gtk.DrawingArea:
        """A preview. ``staged`` shows what the audience would see (board, ink, laser); else the plain slide."""
        area = Gtk.DrawingArea(hexpand=True, vexpand=height is None)
        if height:
            area.set_content_height(height)
        area.set_draw_func(lambda _a, cr, w, h: self._draw_page(cr, get_page(), w, h, staged))
        (self._stage_areas if staged else self._plain_areas).append(area)
        return area

    def _draw_page(self, cr, page: int, width: int, height: int, staged: bool = False) -> None:
        if not 0 <= page < self.doc.pages:
            return
        if staged:
            self.stage.draw(cr, page, width, height)
        else:
            self.doc.draw(cr, page, width, height)

    def _big_preview(self) -> Gtk.DrawingArea:
        """The large preview of the viewed page: draw on it with a pen, aim the laser with the pointer."""
        area = self._page_area(lambda: self.deck.view)
        if "ink" in self.projector.caps:  # a plain PDF viewer as projector cannot show ink
            InkInput(area, self.stage, self.ink, lambda: self.deck.view)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _c, x, y: self._laser_motion(area, x, y))
        motion.connect("leave", lambda _c: self.deck.set_laser(None))
        area.add_controller(motion)
        return area

    def _laser_motion(self, area: Gtk.DrawingArea, x: float, y: float) -> None:
        if self.deck.laser_on:
            self.deck.set_laser(self.stage.to_fraction(self.deck.view, area.get_width(), area.get_height(), x, y))

    def _captioned(self, caption: str, get_page, height: int, *, staged: bool) -> Gtk.Box:
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        column.append(Gtk.Label(label=caption, css_classes=["dim-label", "caption"]))
        column.append(self._page_area(get_page, height, staged=staged))
        return column

    def _notes_widget(self) -> Gtk.ScrolledWindow:
        """A scrolling view of the shared notes buffer; each layout gets its own view."""
        view = Gtk.TextView(
            buffer=self.buffer, editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=12, right_margin=12, vexpand=True,
        )  # fmt: skip
        scroller = Gtk.ScrolledWindow(child=view)
        scroller.get_vadjustment().connect("value-changed", lambda _a: self._mark_dirty())
        self.view, self.scroller = view, scroller
        return scroller

    def _paned(self, start: Gtk.Widget, end: Gtk.Widget, position: int) -> Gtk.Paned:
        paned = Gtk.Paned(start_child=start, end_child=end, position=position, resize_start_child=True)
        paned.connect("notify::position", lambda p, _s: self._remember_pane(p))
        self.paned = paned
        return paned

    def _remember_pane(self, paned: Gtk.Paned) -> None:
        if not self._fitting:  # only a user drag counts as a chosen split
            self._pane[self.layout_active] = paned.get_position()
            self._mark_dirty()

    def _build_compact(self) -> Gtk.Paned:
        """Notebook layout: big preview with audience and next below it, notes on the right."""
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.append(self._big_preview())
        small = Gtk.Box(spacing=6, homogeneous=True)
        small.append(self._captioned(tr("audience"), lambda: self.deck.page, SMALL_H, staged=True))
        small.append(self._captioned(tr("next"), lambda: self.deck.view + 1, SMALL_H, staged=False))
        left.append(small)
        return self._paned(left, self._notes_widget(), self._pane.get(layouts.COMPACT, 460))

    def _build_wide(self) -> Gtk.Box:
        """Big-screen layout: large slide, a bigger next slide and tall notes, and a filmstrip underneath."""
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row = Gtk.Box(spacing=6, homogeneous=True)
        row.append(self._captioned(tr("audience"), lambda: self.deck.page, WIDE_ROW_H, staged=True))
        row.append(self._captioned(tr("next"), lambda: self.deck.view + 1, WIDE_ROW_H, staged=False))
        right.append(row)
        right.append(self._notes_widget())
        width = self.get_width() or self.get_default_size()[0]
        top = self._paned(self._big_preview(), right, self._pane.get(layouts.WIDE, int(width * 0.58)))
        top.set_vexpand(True)
        self._strip_box = Gtk.Box(
            spacing=layouts.STRIP_GAP_PX, margin_start=layouts.STRIP_GAP_PX, margin_top=4, margin_bottom=4
        )
        strip = Gtk.ScrolledWindow(child=self._strip_box, vscrollbar_policy=Gtk.PolicyType.NEVER)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        column.append(top)
        column.append(strip)
        return column

    def _apply_layout(self, *, force: bool = False) -> None:
        """Show the layout the mode and window width call for, rebuilding the main page only when it changes."""
        width = self.get_width() or self.get_default_size()[0]
        active = layouts.resolve(self.layout_mode, width, self.layout_active)
        if not force and active == self.layout_active:
            return
        keep = self.scroller.get_vadjustment().get_value() if self.scroller is not None else 0.0
        self.layout_active = active
        self._stage_areas.clear()
        self._plain_areas.clear()
        self._strip_box = None
        child = self.main_holder.get_first_child()
        if child is not None:
            self.main_holder.remove(child)
        self.main_holder.append(self._build_wide() if active == layouts.WIDE else self._build_compact())
        GLib.idle_add(self._after_layout, keep)
        self._refresh_strip()
        self._mark_current_section()
        self._sync_actions()

    def _after_layout(self, keep: float) -> bool:
        """After a rebuild, line wrapping differs: realign to the current slide's notes, else restore the offset."""
        if self.scroller is not None:
            current = self._current_section()
            if current is not None:
                self._scroll_to_section(current)
            else:
                self.scroller.get_vadjustment().set_value(keep)
        return False

    def _fit_pane(self) -> None:
        """Until the user drags the splitter, the wide layout gives the slide 58% of the window width."""
        if self.layout_active != layouts.WIDE or layouts.WIDE in self._pane or self.paned is None:
            return
        want = round(self.get_width() * WIDE_SLIDE_SHARE)
        if want > 0 and abs(self.paned.get_position() - want) > PANE_TOLERANCE_PX:
            self._fitting = True
            self.paned.set_position(want)
            self._fitting = False

    def _refresh_strip(self) -> None:
        """Rebuild the filmstrip: ``previous`` slides, the viewed one, and ``upcoming`` ones."""
        box = self._strip_box
        if box is None:
            return
        pages = layouts.strip_pages(self.deck.view, self.deck.pages, self.previous, self.upcoming)
        tw = layouts.thumb_width(max(self.get_width(), 400), len(pages))
        pw, ph = self.doc.page_size(0)
        th = max(40, round(tw * ph / pw))
        child = box.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            box.remove(child)
            child = following
        for page in pages:
            box.append(self._strip_thumb(page, tw, th))

    def _strip_thumb(self, page: int, width: int, height: int) -> Gtk.DrawingArea:
        area = Gtk.DrawingArea(
            content_width=width, content_height=height, tooltip_text=tr("slide {n}").format(n=page + 1)
        )
        area.set_draw_func(lambda _a, cr, w, h: self._draw_thumb(cr, page, w, h))
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.execute(f"goto {page + 1}"))
        area.add_controller(click)
        return area

    def _draw_thumb(self, cr, page: int, width: int, height: int) -> None:
        cr.set_source_surface(self.doc.thumbnail(page, width, height), 0, 0)
        cr.paint()
        if page == self.deck.view:
            cr.set_source_rgb(*ACCENT_RGB)
            cr.set_line_width(4)
            cr.rectangle(2, 2, width - 4, height - 4)
            cr.stroke()
        if page == self.deck.page:  # what the audience sees right now
            cr.set_source_rgb(*LIVE_RGB)
            cr.arc(width - 10, 10, 5, 0, 6.2832)
            cr.fill()
        cr.select_font_face("sans")
        cr.set_font_size(11)
        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.rectangle(0, height - 16, 26, 16)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(4, height - 4)
        cr.show_text(str(page + 1))

    def _build_overview(self) -> Gtk.ScrolledWindow:
        self.flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.SINGLE, activate_on_single_click=False, homogeneous=True,
            max_children_per_line=12,
        )  # fmt: skip
        self.flow.connect("child-activated", self._overview_pick)  # double click or Enter: go there and leave
        self.flow.connect("selected-children-changed", self._overview_preview)  # single click: look at it
        return Gtk.ScrolledWindow(child=self.flow)

    def _build_search(self) -> Gtk.Revealer:
        self.search_entry = Gtk.SearchEntry(placeholder_text=tr("Search slides and notes, Enter to run"), hexpand=True)
        self.search_entry.connect("activate", self._run_search)
        self.results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        self.results.connect("row-activated", lambda _l, row: self._pick_hit(row.get_index()))
        scroller = Gtk.ScrolledWindow(
            child=self.results, max_content_height=SEARCH_PANEL_H, propagate_natural_height=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )  # fmt: skip
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        box.append(self.search_entry)
        box.append(scroller)
        self.search_revealer = Gtk.Revealer(child=box, transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        return self.search_revealer

    # ---- deck and timer ----
    def _on_deck(self) -> None:
        proj = f" (proj {self.deck.page + 1})" if self.deck.page != self.deck.view else ""
        self.pos.set_label(f"{self.deck.view + 1} / {self.deck.pages}{proj}")
        self.title_pos.set_label(f"{self.deck.view + 1} / {self.deck.pages}")
        for area in (*self._stage_areas, *self._plain_areas):
            area.queue_draw()
        self._refresh_strip()
        self._sync_actions()
        self._mark_current_section()
        self._mark_dirty()

    def _on_ink(self) -> None:
        for area in self._stage_areas:
            area.queue_draw()
        self._sync_actions()

    def _mark_dirty(self) -> None:
        self.dirty = True

    def _goto_entry(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if text.isdigit():
            self.deck.goto(int(text) - 1)
        entry.set_text("")
        self.set_focus(None)

    def _toggle_timer(self) -> None:
        self.timer.toggle(time.time())
        self._mark_dirty()
        self._tick()

    def _reset_timer(self) -> None:
        self.timer.reset()
        self._mark_dirty()
        self._tick()

    def _tick(self) -> bool:
        now = time.time()
        self.timer_label.set_label(
            f"{format_seconds(self.timer.elapsed(now))} / {format_seconds(self.timer.left(now))}"
        )
        self.timer_icon.set_from_icon_name(
            "media-playback-pause-symbolic" if self.timer.running else "media-playback-start-symbolic"
        )
        if self.timer.running:
            self.timer_button.add_css_class("suggested-action")
        else:
            self.timer_button.remove_css_class("suggested-action")
        self._apply_layout()
        self._fit_pane()
        self.info.set_label(schedule_summary(self.timer, now, self.deck.view, self.deck.pages))
        return True

    # ---- fullscreen ----
    def _set_console_fullscreen(self, on: bool) -> None:
        if on:
            self.fullscreen()
        else:
            self.unfullscreen()

    # ---- pages: overview and search ----
    def _show(self, name: str) -> None:
        self.stack.set_visible_child_name(name)

    def show_main(self) -> None:
        """Back to the slides: close the command line, search and overview (a cancelled overview restores the view)."""
        self.cmd.set_visible(False)
        self.search_revealer.set_reveal_child(False)
        if self._overview_origin is not None:
            self.deck.peek(self._overview_origin)  # leaving the overview without choosing: previous condition
            self._overview_origin = None
        self._show("main")
        self.set_focus(None)

    def show_overview(self) -> None:
        """Thumbnails of all slides: a click looks at one, a double click goes there, Esc or the button cancels."""
        if self.stack.get_visible_child_name() == "overview":
            self.show_main()
            return
        self.search_revealer.set_reveal_child(False)
        if self._flow_pages() != self.doc.pages:
            self.flow.remove_all()
            for i in range(self.doc.pages):
                self.flow.append(self._thumbnail(i))
        self._overview_origin = self.deck.view
        current = self.flow.get_child_at_index(self.deck.view)
        if current is not None:
            self._overview_busy = True
            self.flow.select_child(current)
            self._overview_busy = False
        self._show("overview")

    def _overview_preview(self, flow: Gtk.FlowBox) -> None:
        selected = flow.get_selected_children()
        if selected and not self._overview_busy:
            self.deck.peek(selected[0].get_index())  # look only; the projector stays where it is

    def _overview_pick(self, _flow: Gtk.FlowBox, child: Gtk.FlowBoxChild) -> None:
        self._overview_origin = None  # a deliberate choice: do not restore
        self.deck.goto(child.get_index())
        self.show_main()

    def _flow_pages(self) -> int:
        count = 0
        while self.flow.get_child_at_index(count) is not None:
            count += 1
        return count

    def _thumbnail(self, page: int) -> Gtk.Overlay:
        area = Gtk.DrawingArea(content_width=THUMB_W, content_height=THUMB_H)
        area.set_draw_func(lambda _a, cr, w, h: self._draw_page(cr, page, w, h))  # drawn only when visible
        label = Gtk.Label(label=str(page + 1), halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
        overlay = Gtk.Overlay(child=area)
        overlay.add_overlay(label)
        return overlay

    def show_search(self, *, toggle: bool = True) -> None:
        """Open the search panel above the slides (or close it again when ``toggle`` and it is open)."""
        if toggle and self.search_revealer.get_reveal_child():
            self.show_main()
            return
        self.search_revealer.set_reveal_child(True)
        self.search_entry.grab_focus()

    def _run_search(self, entry: Gtk.SearchEntry) -> None:
        self.hits = search.find(entry.get_text(), self.doc.texts(), [(s.slide, s.text) for s in self._sections])
        self.hit = -1
        self.results.remove_all()
        for h in self.hits:
            kind = tr("Slide {n}").format(n=h.slide)
            if h.kind != "slide":
                kind = tr("Notes (slide {n})").format(n=h.slide) if h.slide else tr("Notes")
            row = Adw.ActionRow(title=kind, subtitle=GLib.markup_escape_text(h.snippet), activatable=True)
            row.set_subtitle_lines(2)
            self.results.append(row)
        if not self.hits:
            self.results.append(Adw.ActionRow(title=tr("No matches"), activatable=False))

    def show_help(self) -> None:
        """A page listing every command with usage, key and description; picking one starts typing it."""
        unsupported = {name for name, cap in COMMAND_CAPS.items() if cap not in self.projector.caps}
        page = Adw.PreferencesPage()
        intro = tr("Open the command line with : (Tab completes), or pick a row to start typing it.")
        page.add(Adw.PreferencesGroup(title=tr("Commands"), description=intro))
        groups: dict[str, Adw.PreferencesGroup] = {}
        for group, usage, text, key in commands.help_entries(self._commands, key_for):
            if group not in groups:
                groups[group] = Adw.PreferencesGroup(title=tr(group))
                page.add(groups[group])
            name = usage.split()[0]
            note = tr("  (not supported by this projector)") if name in unsupported else ""
            row = Adw.ActionRow(
                title=GLib.markup_escape_text(usage),
                subtitle=GLib.markup_escape_text(tr(text) + note),
                activatable=True,
            )
            if key:
                row.add_suffix(Gtk.Label(label=key, css_classes=["dim-label", "monospace"]))
            row.connect("activated", lambda _r, n=name: self._help_pick(n))
            groups[group].add(row)
        old = self.stack.get_child_by_name("help")
        if old is not None:
            self.stack.remove(old)
        self.stack.add_named(page, "help")
        self._show("help")

    def _help_pick(self, name: str) -> None:
        self.show_main()
        self._open_command(f":{name} ")

    def _pick_hit(self, index: int) -> None:
        if index < len(self.hits):
            self.show_hit(index)  # the panel stays open so you can step through the other hits

    def show_hit(self, index: int) -> None:
        """Jump to a search hit: slide hits move the view, note hits scroll the notes."""
        if not self.hits:
            return
        self.hit = index % len(self.hits)
        h = self.hits[self.hit]
        self.buffer.remove_tag_by_name("hit", self.buffer.get_start_iter(), self.buffer.get_end_iter())
        if h.kind == "slide":
            self.deck.goto(h.index)
            return
        if h.slide and self.show_slide_on:
            self.deck.peek(h.slide - 1)  # preview only: the projector is not moved
        self._scroll_to_section(h.index)  # after peek, which scrolls to the slide's own section
        self.buffer.apply_tag_by_name("hit", *self._section_range(h.index))

    # ---- commands and keys ----
    def _build_commands(self) -> dict[str, Callable[[str], None]]:
        deck, c, t = self.deck, commands, self.tools
        table = {
            "next": lambda a: deck.step(c.count(a)),
            "prev": lambda a: deck.step(-c.count(a)),
            "goto": self._cmd_goto,
            "first": lambda _a: deck.goto(0),
            "last": lambda _a: deck.goto(deck.pages - 1),
            "scroll-down": lambda a: self._scroll(c.count(a)),
            "scroll-up": lambda a: self._scroll(-c.count(a)),
            "search": self._cmd_search,
            "hit-next": lambda _a: self.show_hit(self.hit + 1),
            "hit-prev": lambda _a: self.show_hit(self.hit - 1),
            "show-slide": lambda a: self._set_pref("show_slide_on", c.flag(a, self.show_slide_on)),
            "overview": lambda _a: self.show_overview(),
            "main": lambda _a: self.show_main(),
            "freeze": lambda a: deck.set_frozen(c.flag(a, deck.frozen)),
            "blackout": lambda a: self._cmd_blackout(c.flag(a, deck.blackout)),
            "timer": lambda _a: self._toggle_timer(),
            "timer-reset": lambda _a: self._reset_timer(),
            "target": self._cmd_target,
            "fullscreen": lambda a: self._set_console_fullscreen(c.flag(a, self.is_fullscreen())),
            "projector-fullscreen": lambda a: self.projector.fullscreen(c.flag(a, self.projector.is_fullscreen())),
            "vim": lambda a: self._set_pref("vim_on", c.flag(a, self.vim_on)),
            "layout": self._cmd_layout,
            "upcoming": lambda a: self._cmd_count("upcoming", a, layouts.MAX_UPCOMING),
            "previous": lambda a: self._cmd_count("previous", a, layouts.MAX_PREVIOUS),
            "clear": lambda _a: self.ink.clear(self._view_layer()),
            "undo": lambda _a: self.ink.undo(self._view_layer()),
            "redo": lambda _a: self.ink.redo(self._view_layer()),
            "clear-all": lambda _a: self._cmd_clear_all(),
            "restore-all": lambda _a: self._tool(t.restore_all),
            "draw": lambda a: self._set_tool("mouse_draw", c.flag(a, self.ink.tool.mouse_draw)),
            "eraser": lambda a: self._set_tool("eraser", c.flag(a, self.ink.tool.eraser)),
            "highlighter": lambda a: self._tool(t.highlighter, c.flag(a, self.ink.tool.highlighter)),
            "color": lambda a: self._tool(t.color, a),
            "width": lambda a: self._tool(t.width, a),
            "smooth": lambda a: self._tool(t.smoothing, a),
            "eraser-size": lambda a: self._tool(t.eraser_size, a),
            "highlight-alpha": lambda a: self._tool(t.highlight_alpha, a),
            "board": lambda a: self._cmd_board(c.flag(a, deck.board)),
            "board-style": lambda a: self._tool(t.board_style, a),
            "laser": lambda a: deck.set_laser_on(c.flag(a, deck.laser_on)),
            "laser-color": lambda a: self._tool(t.laser_color, a),
            "laser-size": lambda a: self._tool(t.laser_size, a),
            "laser-style": lambda a: self._tool(t.laser_style, a),
            "export": self._cmd_export,
            "help": self._cmd_help,
            "quit": lambda _a: self.close(),
        }
        return apply_caps(table, self.projector.caps, self._set_status)

    def execute(self, line: str) -> None:
        """Run one command line, the single path used by buttons, keys and the ``:`` entry."""
        name, arg = commands.parse(line)
        handler = self._commands.get(name)
        if handler is None:
            self._set_status(tr("unknown command: {name} (:help lists them)").format(name=name))
            return
        self._set_status("")
        handler(arg)

    def _set_pref(self, name: str, value: bool) -> None:
        setattr(self, name, value)
        self._sync_actions()
        self._mark_dirty()

    def _cmd_layout(self, arg: str) -> None:
        mode = arg or layouts.AUTO
        if mode == "toggle":
            mode = layouts.COMPACT if self.layout_active == layouts.WIDE else layouts.WIDE
        if mode not in layouts.MODES:
            self._set_status(tr("layout: auto, compact, wide or toggle"))
            return
        self.layout_mode = mode
        self._apply_layout()
        self._sync_actions()
        self._mark_dirty()

    def _cmd_count(self, name: str, arg: str, maximum: int) -> None:
        if not arg.isdigit():
            self._set_status(tr("{name} needs a number 0..{maximum}").format(name=name, maximum=maximum))
            return
        setattr(self, name, layouts.clamp_count(int(arg), maximum))
        self._refresh_strip()
        self._sync_actions()
        self._mark_dirty()

    def _cmd_goto(self, arg: str) -> None:
        if arg.isdigit():
            self.deck.goto(int(arg) - 1)
        else:
            self._set_status(tr("goto needs a slide number"))

    def _cmd_target(self, arg: str) -> None:
        minutes = parse_minutes(arg)
        if minutes is None:
            self._set_status(tr("target needs a length like 90, 1h30, 1:30 or 45m (at most 24 h)"))
            return
        self.timer.target_min = minutes
        self._sync_actions()
        self._mark_dirty()

    def _view_layer(self) -> str:
        return self.stage.layer(self.deck.view)

    def _set_tool(self, name: str, value: bool) -> None:
        setattr(self.ink.tool, name, value)
        self.ink.notify()
        off, on = TOOL_FLAG_MESSAGES[name]
        self._set_status(tr(on if value else off))

    def _tool(self, action: Callable[..., str], *args: object) -> None:
        """Run a pen/board/laser setting from ``Tools`` and show what it did."""
        self._set_status(action(*args))
        self._sync_actions()

    def _cmd_clear_all(self) -> None:
        message = self.tools.clear_all()
        self._set_status(message, undo=bool(self.ink.last_cleared))
        self._sync_actions()

    def _cmd_export(self, arg: str) -> None:
        base = Path(arg).expanduser() if arg else self.doc.path.with_name(f"{self.doc.path.stem}-annotated.pdf")
        target = unique(base)  # never overwrite an existing file
        try:
            pages = self.stage.export_pdf(target)
        except (OSError, cairo.Error) as exc:
            self._set_status(tr("export failed: {error}").format(error=exc))
            return
        self._set_status(tr("wrote {path} ({pages} pages)").format(path=target, pages=pages))

    def _cmd_help(self, arg: str) -> None:
        if arg:
            self._set_status(commands.describe(arg, key_for))
        else:
            self.show_help()

    def _cmd_board(self, on: bool) -> None:
        if on != self.deck.board:
            self.deck.toggle_board()

    def _cmd_blackout(self, on: bool) -> None:
        if on != self.deck.blackout:
            self.deck.toggle_blackout()

    def _cmd_search(self, arg: str) -> None:
        self.show_search(toggle=not arg)
        if arg:
            self.search_entry.set_text(arg)
            self._run_search(self.search_entry)

    def _run_command(self, entry: Gtk.Entry) -> None:
        line = entry.get_text()
        self.show_main()
        self.execute(line)

    def _cmd_key(self, _c: Gtk.EventControllerKey, keyval: int, _code: int, _state: Gdk.ModifierType) -> bool:
        if keyval not in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            return False
        line, matches = commands.complete(self.cmd.get_text(), self._commands)
        self.cmd.set_text(line)
        self.cmd.set_position(-1)
        self._set_status("  ".join(matches) if len(matches) > 1 else "")
        return True  # never let Tab move focus away from the command line

    def say(self, message: str) -> None:
        """Show a message to the presenter."""
        self._set_status(message)

    def _on_key(self, _c: Gtk.EventControllerKey, keyval: int, _code: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.vim.reset()
            self.show_main()
            return True
        if isinstance(self.get_focus(), Gtk.Editable) or state & (
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK
        ):
            return False
        keymap = {
            Gdk.KEY_Right: "next", Gdk.KEY_space: "next", Gdk.KEY_Page_Down: "next",
            Gdk.KEY_Left: "prev", Gdk.KEY_Page_Up: "prev", Gdk.KEY_Home: "first", Gdk.KEY_End: "last",
        }  # fmt: skip
        if keyval in keymap:
            self.execute(keymap[keyval])
            return True
        return self.vim_on and self._vim_key(keyval)

    def _vim_key(self, keyval: int) -> bool:
        char = chr(Gdk.keyval_to_unicode(keyval) or 0)
        action = self.vim.feed(char) if char else None
        if action is None:
            return False
        if action.name == "command-line":
            self._open_command()
        elif action.name != "pending":
            arg = "" if action.count is None else str(action.count)
            self.execute(f"{action.name} {arg}")
        return True

    def _open_command(self, prefill: str = ":") -> None:
        self.cmd.set_visible(True)
        self.cmd.set_text(prefill)
        self.cmd.grab_focus()
        self.cmd.set_position(-1)

    def _scroll(self, lines: int) -> None:
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_value() + lines * SCROLL_STEP)

    # ---- notes ----
    def poll_notes(self) -> None:
        """Reload and re-render the notes when the file changed."""
        if self.notes is None:
            return
        try:
            mtime = self.notes.stamp()
            if mtime == self._notes_mtime:
                return
            self._sections = self.notes.load()
        except (NotesError, OSError) as exc:
            self._set_status(str(exc))
            return
        self._notes_mtime = mtime
        self._rebuild_notes()
        threading.Thread(target=self._compile_math, args=(self._sections, mtime), daemon=True).start()

    def _formulas(self, sections: list[Section]) -> list[mathimg.Formula]:
        spans = [s for sec in sections for s in notes.parse(sec.text)]
        return [mathimg.Formula(s.text, s.style == "display") for s in spans if s.style in ("math", "display")]

    def _compile_math(self, sections: list[Section], mtime: int) -> None:
        images = mathimg.render(self._formulas(sections))
        GLib.idle_add(self._math_ready, images, mtime)

    def _math_ready(self, images: dict[mathimg.Formula, Path], mtime: int) -> bool:
        if mtime != self._notes_mtime:
            return False  # notes changed again while compiling
        try:
            self._textures = {f: Gdk.Texture.new_from_filename(str(p)) for f, p in images.items()}
        except GLib.Error as exc:
            self._set_status(tr("math image error: {error}").format(error=exc.message))
            return False
        self._rebuild_notes()
        return False

    def _rebuild_notes(self) -> None:
        adj = self.scroller.get_vadjustment()
        keep = adj.get_value()
        self.buffer.set_text("")
        for i, section in enumerate(self._sections):
            self.buffer.create_mark(f"sec{i}", self.buffer.get_end_iter(), True)
            for span in notes.parse(section.text):
                self._insert_span(span)
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
        GLib.idle_add(lambda: adj.set_value(keep) and False)
        self._mark_current_section()

    def _insert_span(self, span: notes.Span) -> None:
        end = self.buffer.get_end_iter()
        if span.style in ("math", "display"):
            texture = self._textures.get(mathimg.Formula(span.text, span.style == "display"))
            if texture is not None:
                self.buffer.insert_paintable(end, texture)
                return
            self.buffer.insert_with_tags_by_name(
                end, f"${span.text}$" if span.style == "math" else f"\n{span.text}\n", "raw"
            )
        elif span.style:
            self.buffer.insert_with_tags_by_name(end, span.text, span.style)
        else:
            self.buffer.insert(end, span.text)

    def _section_range(self, index: int) -> tuple[Gtk.TextIter, Gtk.TextIter]:
        start = self.buffer.get_iter_at_mark(self.buffer.get_mark(f"sec{index}"))
        nxt = self.buffer.get_mark(f"sec{index + 1}")
        return start, self.buffer.get_iter_at_mark(nxt) if nxt else self.buffer.get_end_iter()

    def _scroll_to_section(self, index: int) -> None:
        mark = self.buffer.get_mark(f"sec{index}")
        if mark is not None:
            self.view.scroll_to_mark(mark, 0.0, True, 0.0, 0.0)

    def _current_section(self) -> int | None:
        """Index of the first notes section tied to the viewed slide."""
        return next((i for i, sec in enumerate(self._sections) if sec.slide == self.deck.view + 1), None)

    def _mark_current_section(self) -> None:
        if not self._sections:
            return
        self.buffer.remove_tag_by_name("current", self.buffer.get_start_iter(), self.buffer.get_end_iter())
        for i, section in enumerate(self._sections):
            if section.slide == self.deck.view + 1:
                self.buffer.apply_tag_by_name("current", *self._section_range(i))
        first = self._current_section()
        if first is not None:
            self._scroll_to_section(first)

    # ---- recovery ----
    def snapshot(self) -> dict[str, object]:
        """State written to disk: pages, timer, notes position, pane splits, layout and preferences."""
        return {
            **self.deck.to_dict(),
            "timer": self.timer.to_dict(),
            "notes_scroll": self.scroller.get_vadjustment().get_value() if self.scroller else 0.0,
            "panes": dict(self._pane),
            "layout": self.layout_mode,
            "previous": self.previous,
            "upcoming": self.upcoming,
            "vim": self.vim_on,
        }

    def restore(self, saved: dict[str, object]) -> None:
        """Apply saved console state (the deck is restored separately)."""
        self.timer.load(saved.get("timer"))
        self._restore_view(saved)
        scroll = saved.get("notes_scroll")
        if isinstance(scroll, int | float) and not isinstance(scroll, bool):
            GLib.idle_add(lambda: self.scroller.get_vadjustment().set_value(scroll) and False)
        if isinstance(saved.get("vim"), bool):
            self.vim_on = bool(saved["vim"])
        self._sync_actions()
        self._tick()
        self.dirty = False

    def _restore_view(self, saved: dict[str, object]) -> None:
        panes = saved.get("panes")
        if isinstance(panes, dict):
            self._pane.update(
                {k: v for k, v in panes.items() if k in (layouts.COMPACT, layouts.WIDE) and isinstance(v, int)}
            )
        mode = saved.get("layout")
        if mode in layouts.MODES:
            self.layout_mode = str(mode)
        for name, maximum in (("previous", layouts.MAX_PREVIOUS), ("upcoming", layouts.MAX_UPCOMING)):
            value = saved.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                setattr(self, name, layouts.clamp_count(value, maximum))
        self._apply_layout(force=True)

"""Projector window: what the audience sees, with the configured blackout screen."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from lectos.config import Blackout
from lectos.draw.stage import Stage
from lectos.gtk.inkinput import InkInput
from lectos.i18n import tr
from lectos.model.ink import Ink
from lectos.projectors.projection import GTK_CAPS

PROJECTOR_ICON = "lectos-projector"


class ProjectorWindow(Gtk.ApplicationWindow):
    """Shows the stage for ``deck.page`` fitted to the window; draws under pen or ``draw on`` mouse."""

    def __init__(
        self,
        app: Gtk.Application,
        stage: Stage,
        ink: Ink,
        monitor: Gdk.Monitor | None,
        blackout: Blackout,
        *,
        name: str = "",
    ) -> None:
        super().__init__(
            application=app,
            title=tr("lectos projector - {name}").format(name=name),
            icon_name=PROJECTOR_ICON,
            default_width=960,
            default_height=540,
        )
        self.stage, self.deck, self.ink, self.monitor = stage, stage.deck, ink, monitor
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        overlay = Gtk.Overlay(child=self.area)
        self.standby = self._build_standby(blackout)
        if self.standby is not None:
            overlay.add_overlay(self.standby)
        self.set_child(overlay)
        InkInput(self.area, stage, ink, lambda: self.deck.page)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, *_: self._on_key(keyval))
        self.add_controller(keys)
        self.deck.subscribe(self._on_deck)
        ink.subscribe(self.area.queue_draw)

    def _build_standby(self, blackout: Blackout) -> Gtk.Box | None:
        """The configured blackout screen, shown over the slide; None means plain black."""
        if not blackout.custom:
            return None
        css = Gtk.CssProvider()
        css.load_from_string(
            f".lectos-standby {{ background: {blackout.background}; }}"
            f".lectos-standby label {{ color: {blackout.text_color}; font-size: 48px; }}"
        )  # colours are validated as #rrggbb by lectos.config
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, css_classes=["lectos-standby"], visible=False)
        if blackout.image is not None:
            picture = Gtk.Picture(vexpand=True, content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, margin_top=24)
            picture.set_filename(str(blackout.image))
            box.append(picture)
        if blackout.text:
            box.append(Gtk.Label(label=blackout.text, vexpand=not blackout.image, margin_bottom=24, wrap=True))
        return box

    def _on_deck(self) -> None:
        if self.standby is not None:
            self.standby.set_visible(self.deck.blackout)
        self.area.queue_draw()

    def set_fullscreen(self, on: bool) -> None:
        """Enter fullscreen on the chosen monitor, or leave it."""
        if not on:
            self.unfullscreen()
        elif self.monitor is not None:
            self.fullscreen_on_monitor(self.monitor)
        else:
            self.fullscreen()

    def _draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        if self.deck.blackout:
            cr.set_source_rgb(0, 0, 0)
            cr.paint()
            return
        self.stage.draw(cr, self.deck.page, width, height)

    def _on_key(self, keyval: int) -> bool:
        actions = {
            Gdk.KEY_f: lambda: self.set_fullscreen(not self.is_fullscreen()),
            Gdk.KEY_F11: lambda: self.set_fullscreen(not self.is_fullscreen()),
            Gdk.KEY_b: self.deck.toggle_blackout,
            Gdk.KEY_c: lambda: self.ink.clear(self.stage.layer(self.deck.page)),
            Gdk.KEY_Escape: lambda: self.set_fullscreen(False),
            Gdk.KEY_Right: lambda: self.deck.step(1),
            Gdk.KEY_space: lambda: self.deck.step(1),
            Gdk.KEY_Left: lambda: self.deck.step(-1),
        }
        action = actions.get(keyval)
        if action is None:
            return False
        action()
        return True


class WindowProjector:
    """Adapts ``ProjectorWindow`` to the ``Projector`` protocol. The window follows the deck by itself."""

    caps = GTK_CAPS

    def __init__(self, window: ProjectorWindow) -> None:
        self.window = window

    def goto(self, page: int) -> None:
        """Nothing to do: the window redraws from the shared deck."""

    def fullscreen(self, on: bool) -> None:
        """Enter or leave fullscreen."""
        self.window.set_fullscreen(on)

    def is_fullscreen(self) -> bool:
        """Whether the window is fullscreen."""
        return self.window.is_fullscreen()

    def stop(self) -> None:
        """Close the window."""
        self.window.close()

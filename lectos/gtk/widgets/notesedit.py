"""Editor for the notes of one slide: plain text in, plain text out. The caller decides where it is saved."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from lectos.i18n import tr


class NotesEditor(Adw.Window):
    """A window with the slide's notes text; Save hands the text to ``on_save``, Cancel or Esc drops it."""

    def __init__(self, parent: Gtk.Window, slide: int, text: str, on_save: Callable[[str], None]) -> None:
        super().__init__(
            title=tr("Notes for slide {n}").format(n=slide),
            transient_for=parent,
            modal=True,
            default_width=620,
            default_height=480,
        )
        self.on_save = on_save
        self.view = Gtk.TextView(
            monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=12, right_margin=12, top_margin=8
        )
        self.view.get_buffer().set_text(text)
        save = Gtk.Button(label=tr("Save"), css_classes=["suggested-action"], tooltip_text=tr("Save (Ctrl+Enter)"))
        save.connect("clicked", lambda _b: self.save())
        cancel = Gtk.Button(label=tr("Cancel"), tooltip_text=tr("Discard (Esc)"))
        cancel.connect("clicked", lambda _b: self.close())
        bar = Adw.HeaderBar()
        bar.pack_start(cancel)
        bar.pack_end(save)
        toolbar = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=self.view))
        toolbar.add_top_bar(bar)
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.view.grab_focus()

    def text(self) -> str:
        """The text as edited."""
        buffer = self.view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    def save(self) -> None:
        """Hand the text over and close."""
        self.on_save(self.text())
        self.close()

    def _on_key(self, _c: Gtk.EventControllerKey, keyval: int, _code: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.CONTROL_MASK:
            self.save()
            return True
        return False

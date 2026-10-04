# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GObject, Pango

from stilonotes.models import Note
from stilonotes.category_header_bar import CategoryHeaderBar


class SelectionHeaderBar(Adw.Bin):
    __gtype_name__ = "SelectionHeaderBar"

    __gsignals__ = {
        "abort": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "set-favourite": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "export": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "categories-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "select-all": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self._selected_notes: List[Note] = []
        self._active: bool = False
        self._build_ui()

    def _build_ui(self):
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Main Selection HeaderBar
        self._main_header_bar = Adw.HeaderBar()
        self._main_header_bar.set_show_start_title_buttons(False)
        self._main_header_bar.set_show_end_title_buttons(False)
        self._main_header_bar.set_show_back_button(False)

        # Back button [start]
        self.back_btn = Gtk.Button()
        self.back_btn.set_icon_name("go-previous-symbolic")
        self.back_btn.set_tooltip_text("Back (Esc)")
        self.back_btn.connect("clicked", lambda _b: self.emit("abort"))
        self._main_header_bar.pack_start(self.back_btn)

        # Select All button [start]
        self.select_all_btn = Gtk.Button()
        self.select_all_btn.set_icon_name("edit-select-all-symbolic")
        self.select_all_btn.set_tooltip_text("Select All (Ctrl+A)")
        self.select_all_btn.connect("clicked", lambda _b: self.emit("select-all"))
        self._main_header_bar.pack_start(self.select_all_btn)

        # Title: "{n} Selected"
        self._count_label = Gtk.Label(label="0 Selected")
        self._count_label.add_css_class("title")
        self._count_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._main_header_bar.set_title_widget(self._count_label)

        # Action Buttons [end]
        # In GTK pack_end: items packed first are furthest to the right.
        # Order: Delete (rightmost), Export, Favorite, Category (innermost).
        # Visual display from left to right: [Category] [Favorite] [Export] [Delete]

        # Delete button
        self.delete_btn = Gtk.Button()
        self.delete_btn.set_icon_name("user-trash-symbolic")
        self.delete_btn.set_tooltip_text("Delete Selected")
        self.delete_btn.add_css_class("destructive-action")
        self.delete_btn.connect("clicked", lambda _b: self.emit("delete"))
        self._main_header_bar.pack_end(self.delete_btn)

        # Export button
        self.export_btn = Gtk.Button()
        self.export_btn.set_icon_name("document-save-as-symbolic")
        self.export_btn.set_tooltip_text("Export Selected")
        self.export_btn.connect("clicked", lambda _b: self.emit("export"))
        self._main_header_bar.pack_end(self.export_btn)

        # Favorite button
        self.favorite_btn = Gtk.Button()
        self.favorite_btn.set_icon_name("starred-symbolic")
        self.favorite_btn.set_tooltip_text("Toggle Favorite for Selected")
        self.favorite_btn.connect("clicked", lambda _b: self.emit("set-favourite"))
        self._main_header_bar.pack_end(self.favorite_btn)

        # Category button
        self.category_btn = Gtk.Button()
        self.category_btn.set_icon_name("folder-symbolic")
        self.category_btn.set_tooltip_text("Change Category for Selected")
        self.category_btn.connect("clicked", lambda _b: self.edit_category_for_selection())
        self._main_header_bar.pack_end(self.category_btn)

        self._stack.add_named(self._main_header_bar, "main")

        # 2. Category HeaderBar
        self._category_header_bar = CategoryHeaderBar()
        self._category_header_bar.connect("category-changed", self._on_category_changed)
        self._category_header_bar.connect("abort", self._on_category_abort)
        self._stack.add_named(self._category_header_bar, "category")

        self.set_child(self._stack)
        self._refresh()

    def activate(self):
        """Activate selection header bar."""
        self._stack.set_visible_child_name("main")
        self._active = True
        self._selected_notes = []
        self._refresh()

    def deactivate(self):
        """Deactivate selection header bar."""
        self._active = False
        self._selected_notes = []
        self._stack.set_visible_child_name("main")

    def set_selected_notes(self, notes: List[Note]):
        self._selected_notes = list(notes)
        self._refresh()

    def get_selected_notes(self) -> List[Note]:
        return list(self._selected_notes)

    def set_categories_model(self, categories: List[str]):
        """Supply category suggestions to CategoryHeaderBar."""
        self._category_header_bar.set_categories(categories)

    def edit_category_for_selection(self):
        if not self._selected_notes:
            return
        # If all selected notes have the same category, prefill it
        first_cat = (self._selected_notes[0].category or "").strip()
        if first_cat.lower() == "uncategorized":
            first_cat = ""
        all_same = all(((n.category or "").strip().lower() == first_cat.lower()) for n in self._selected_notes)
        initial_cat = first_cat if all_same else ""

        self._stack.set_visible_child_name("category")
        self._category_header_bar.activate(initial_cat)

    def _on_category_changed(self, _chb, new_category: str):
        clean_cat = (new_category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""
        self._stack.set_visible_child_name("main")
        self.emit("categories-changed", clean_cat)

    def _on_category_abort(self, _chb):
        self._stack.set_visible_child_name("main")

    def _refresh(self):
        count = len(self._selected_notes)
        self._count_label.set_text(f"{count} Selected")
        has_sel = count > 0
        self.category_btn.set_sensitive(has_sel)
        self.favorite_btn.set_sensitive(has_sel)
        self.export_btn.set_sensitive(has_sel)
        self.delete_btn.set_sensitive(has_sel)

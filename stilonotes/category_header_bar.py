# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List
import warnings

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GObject, Gdk, GLib

warnings.filterwarnings("ignore", category=DeprecationWarning)


class CategoryHeaderBar(Adw.Bin):
    __gtype_name__ = "CategoryHeaderBar"

    __gsignals__ = {
        "category-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "abort": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.add_css_class("background")
        self._build_ui()

    def _build_ui(self):
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_show_start_title_buttons(False)
        self.header_bar.set_show_end_title_buttons(False)
        self.header_bar.set_show_back_button(False)
        self.header_bar.set_hexpand(True)

        # 1. Abort / Revert Button
        self.abort_btn = Gtk.Button()
        self.abort_btn.set_icon_name("edit-undo-symbolic")
        self.abort_btn.set_tooltip_text("Revert Changes (Esc)")
        self.abort_btn.connect("clicked", lambda _b: self.emit("abort"))
        self.header_bar.pack_start(self.abort_btn)

        # 2. Title Widget: Clamped Box containing Entry and Apply button
        clamp = Adw.Clamp()
        clamp.set_hexpand(True)
        clamp.set_maximum_size(440)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Category Entry
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_max_length(500)
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "folder-symbolic")
        self.entry.set_placeholder_text("Category name…")
        self.entry.add_css_class("category-selector")
        self.entry.connect("activate", lambda _e: self._on_apply())
        self.entry.connect("icon-release", lambda _e, _pos: self._show_completion_popup())

        # Setup EntryCompletion with suggestions
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.completion = Gtk.EntryCompletion()
            self.completion.set_inline_completion(True)
            self.completion.set_popup_completion(True)
            self.completion.set_minimum_key_length(0)
            self.completion.set_text_column(0)
            self.completion.connect("match-selected", self._on_match_selected)

            cell = Gtk.CellRendererText()
            cell.set_property("xpad", 8)
            cell.set_property("ypad", 6)
            self.completion.pack_start(cell, False)
            self.completion.add_attribute(cell, "text", 0)

            self.list_store = Gtk.ListStore(str)
            self.completion.set_model(self.list_store)
            self.entry.set_completion(self.completion)

        # Key controller for Escape key to abort
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(key_ctrl)

        box.append(self.entry)

        # Apply Button
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.set_tooltip_text("Apply Changes")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", lambda _b: self._on_apply())
        box.append(self.apply_btn)

        clamp.set_child(box)
        self.header_bar.set_title_widget(clamp)

        # 3. Clear button (red eraser)
        self.clear_btn = Gtk.Button()
        self.clear_btn.set_icon_name("eraser3-symbolic")
        self.clear_btn.set_tooltip_text("Clear and Apply")
        self.clear_btn.add_css_class("destructive-action")
        self.clear_btn.connect("clicked", lambda _b: self._on_clear())
        self.header_bar.pack_end(self.clear_btn)

        self.set_child(self.header_bar)

    def set_categories(self, categories: List[str]):
        """Populate completion suggestions with current categories."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.list_store.clear()
            for cat in sorted(set(categories)):
                if cat and cat.strip():
                    self.list_store.append([cat.strip()])

    def set_category(self, category: str):
        """Set the current category in the entry."""
        self.entry.set_text(category or "")

    def get_category(self) -> str:
        """Get the current category from the entry."""
        return self.entry.get_text().strip()

    def activate(self, current_category: str = ""):
        """Activate the category header bar with current note's category."""
        self.set_category(current_category)
        self.entry.grab_focus()
        self.entry.select_region(0, -1)
        GLib.idle_add(self._show_completion_popup)

    def _show_completion_popup(self):
        """Display the completion popup with suggestions."""
        if not self.get_realized() or not self.entry.get_realized():
            return False
        try:
            self.completion.complete()
            child = self.entry.get_first_child()
            while child and not isinstance(child, Gtk.Popover):
                child = child.get_next_sibling()
            if child:
                child.set_visible(True)
        except Exception:
            pass
        return False

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.emit("abort")
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def _on_match_selected(self, _comp, model, tree_iter):
        selected_cat = model.get_value(tree_iter, 0)
        self.entry.set_text(selected_cat)
        self._on_apply()
        return True

    def _on_apply(self):
        new_category = self.entry.get_text().strip()
        self.emit("category-changed", new_category)

    def _on_clear(self):
        self.entry.set_text("")
        self.emit("category-changed", "")

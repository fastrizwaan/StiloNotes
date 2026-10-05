# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional
import warnings

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GObject, Gdk, GLib, Pango

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
        self._categories: List[str] = []
        self._just_activated = False
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

        # Category Entry with primary folder icon and secondary clear button
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_max_length(500)
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "folder-symbolic")
        self.entry.set_icon_activatable(Gtk.EntryIconPosition.PRIMARY, True)
        self.entry.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, "All Categories")
        self.entry.set_placeholder_text("Category name…")
        self.entry.add_css_class("category-selector")
        self.entry.connect("activate", lambda _e: self._on_apply())
        self.entry.connect("icon-release", self._on_icon_released)
        self.entry.connect("notify::text", self._on_text_changed)

        # Gesture to open suggestions on click
        click_ctrl = Gtk.GestureClick.new()
        click_ctrl.connect("released", lambda _g, _n, _x, _y: self._on_entry_clicked())
        self.entry.add_controller(click_ctrl)

        # Key controller for Escape key to abort and Down arrow for listbox
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(key_ctrl)

        box.append(self.entry)

        # Suggestions Popover attached directly to entry
        self._build_suggestions_popover()

        # ListStore kept for backwards compatibility
        self.list_store = Gtk.ListStore(str)

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
        self._update_clear_icon()

    def _build_suggestions_popover(self):
        """Construct the popover containing matching categories (or all categories)."""
        self.suggestions_popover = Gtk.Popover()
        self.suggestions_popover.set_parent(self.entry)
        self.suggestions_popover.set_position(Gtk.PositionType.BOTTOM)
        self.suggestions_popover.set_autohide(True)
        self.suggestions_popover.set_has_arrow(False)
        self.suggestions_popover.set_focusable(False)

        def on_pop_visible(pop, _param):
            if pop.get_visible():
                self._update_popover_width()
                GLib.idle_add(self._update_popover_width)

        self.suggestions_popover.connect("notify::visible", on_pop_visible)

        self.pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pop_box.set_margin_top(6)
        self.pop_box.set_margin_bottom(6)
        self.pop_box.set_margin_start(0)
        self.pop_box.set_margin_end(0)
        self.pop_box.set_hexpand(True)
        self.pop_box.set_size_request(260, -1)

        pop_header = Gtk.Label(label="Categories")
        pop_header.add_css_class("heading")
        pop_header.set_xalign(0.0)
        pop_header.set_margin_start(8)
        pop_header.set_margin_top(4)
        pop_header.set_margin_bottom(4)
        self.pop_box.append(pop_header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_propagate_natural_height(True)
        scrolled.set_max_content_height(320)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.categories_listbox = Gtk.ListBox()
        self.categories_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.categories_listbox.add_css_class("menu")
        self.categories_listbox.set_hexpand(True)
        self.categories_listbox.connect("row-activated", self._on_category_row_activated)

        listbox_key = Gtk.EventControllerKey.new()
        listbox_key.connect("key-pressed", self._on_listbox_key_pressed)
        self.categories_listbox.add_controller(listbox_key)

        scrolled.set_child(self.categories_listbox)
        self.pop_box.append(scrolled)

        self.suggestions_popover.set_child(self.pop_box)

    def _update_popover_width(self):
        """Ensure the suggestions dropdown matches the width of the entry widget."""
        w = self.entry.get_width()
        if w > 80:
            target_w = max(w - 12, 260)
            self.pop_box.set_size_request(target_w, -1)

    def _is_text_fully_selected(self) -> bool:
        """Check if all text in the entry is currently selected."""
        text = self.entry.get_text()
        if not text:
            return True
        bounds = self.entry.get_selection_bounds()
        if not bounds:
            return False
        if len(bounds) == 3:
            has_sel, start, end = bounds
            if not has_sel:
                return False
            return abs(end - start) >= len(text)
        elif len(bounds) == 2:
            start, end = bounds
            return abs(end - start) >= len(text)
        return False

    def _populate_suggestions(self, filter_text: str = "", show_all: bool = False):
        """Populate the suggestions popover with matching categories (or all categories if show_all)."""
        while True:
            row = self.categories_listbox.get_first_child()
            if row is None:
                break
            self.categories_listbox.remove(row)

        current_cat = self.get_category().strip().lower()
        search = filter_text.strip().lower() if not show_all else ""

        # 'No Category' option at top (shown if show_all or if 'no'/'clear' matches search)
        if show_all or not search or "no category".startswith(search) or "clear".startswith(search):
            none_row = Gtk.ListBoxRow()
            none_row.add_css_class("flat")
            none_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            none_box.set_margin_start(8)
            none_box.set_margin_end(8)
            none_box.set_margin_top(6)
            none_box.set_margin_bottom(6)

            none_icon = Gtk.Image.new_from_icon_name("edit-clear-symbolic")
            none_lbl = Gtk.Label(label="No Category", xalign=0.0)
            none_lbl.set_hexpand(True)
            none_box.append(none_icon)
            none_box.append(none_lbl)

            if not current_cat:
                check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
                none_box.append(check_icon)

            none_row.set_child(none_box)
            none_row._category_value = ""
            self.categories_listbox.append(none_row)

            # Separator row
            sep_row = Gtk.ListBoxRow()
            sep_row.set_selectable(False)
            sep_row.set_activatable(False)
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_margin_top(2)
            sep.set_margin_bottom(2)
            sep_row.set_child(sep)
            self.categories_listbox.append(sep_row)

        matching_cats = []
        for cat in self._categories:
            if not cat or cat.lower() == "uncategorized":
                continue
            if show_all or not search or search in cat.lower():
                matching_cats.append(cat)

        if not matching_cats and not (show_all or not search):
            empty_row = Gtk.ListBoxRow()
            empty_row.set_selectable(False)
            empty_row.set_activatable(False)
            empty_lbl = Gtk.Label(label=f"No categories match '{filter_text}'", xalign=0.0)
            empty_lbl.add_css_class("dimmed")
            empty_lbl.set_margin_start(8)
            empty_lbl.set_margin_end(8)
            empty_lbl.set_margin_top(6)
            empty_lbl.set_margin_bottom(6)
            empty_row.set_child(empty_lbl)
            self.categories_listbox.append(empty_row)
            return

        for cat in matching_cats:
            row = Gtk.ListBoxRow()
            row.add_css_class("flat")
            rbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            rbox.set_margin_start(8)
            rbox.set_margin_end(8)
            rbox.set_margin_top(6)
            rbox.set_margin_bottom(6)

            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            lbl = Gtk.Label(label=cat, xalign=0.0)
            lbl.set_hexpand(True)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            rbox.append(icon)
            rbox.append(lbl)

            if current_cat and cat.lower() == current_cat:
                check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
                rbox.append(check_icon)

            row.set_child(rbox)
            row._category_value = cat
            self.categories_listbox.append(row)

    def _on_category_row_activated(self, _listbox, row):
        if not hasattr(row, "_category_value"):
            return
        cat = row._category_value
        self.entry.set_text(cat)
        self.suggestions_popover.popdown()
        self._on_apply()

    def _can_show_suggestions(self) -> bool:
        """Popovers need a real toplevel and a mapped entry.

        Calling popup() without one triggers Gdk criticals and can crash
        (e.g. when the category bar was never inserted into a window, or when
        set_category() runs while the bar is hidden behind another stack page).
        """
        return self.get_root() is not None and self.entry.get_mapped()

    def _popup_suggestions(self):
        """Show the suggestions popover only when it can be safely displayed."""
        if self._can_show_suggestions():
            self.suggestions_popover.popup()

    def _on_entry_clicked(self):
        show_all = self._is_text_fully_selected() or not self.entry.get_text()
        self._populate_suggestions(filter_text=self.entry.get_text(), show_all=show_all)
        self._update_popover_width()
        self._popup_suggestions()

    def _on_icon_released(self, _entry, icon_pos):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            self.entry.set_text("")
            self.entry.grab_focus()
            self._populate_suggestions(show_all=True)
            self._update_popover_width()
            self._popup_suggestions()
        elif icon_pos == Gtk.EntryIconPosition.PRIMARY:
            self.entry.grab_focus()
            self.entry.select_region(0, -1)
            self._populate_suggestions(show_all=True)
            self._update_popover_width()
            self._popup_suggestions()

    def _on_text_changed(self, _entry, _pspec):
        self._update_clear_icon()
        if self._just_activated:
            self._just_activated = False
            if self._is_text_fully_selected():
                return
        text = self.entry.get_text()
        if not text or self._is_text_fully_selected():
            self._populate_suggestions(show_all=True)
        else:
            self._populate_suggestions(filter_text=text, show_all=False)
        if self._can_show_suggestions():
            self._update_popover_width()
            self._popup_suggestions()

    def _update_clear_icon(self):
        text = self.entry.get_text()
        if text:
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-clear-symbolic")
            self.entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
            self.entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Clear text")
        else:
            self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)
            self.entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, False)

    def set_categories(self, categories: List[str]):
        """Populate completion suggestions with current categories."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.list_store.clear()
            seen = set()
            clean_cats = []
            for cat in sorted(categories or [], key=lambda s: s.lower()):
                if not cat:
                    continue
                clean = cat.strip()
                if not clean or clean.lower() == "uncategorized":
                    continue
                if clean.lower() not in seen:
                    seen.add(clean.lower())
                    clean_cats.append(clean)
                    self.list_store.append([clean])
            self._categories = clean_cats
            self._populate_suggestions(show_all=True)

    def set_category(self, category: str):
        """Set the current category in the entry."""
        clean = (category or "").strip()
        if clean.lower() == "uncategorized":
            clean = ""
        self.entry.set_text(clean)
        self._update_clear_icon()

    def get_category(self) -> str:
        """Get the current category from the entry."""
        cat = self.entry.get_text().strip()
        return "" if cat.lower() == "uncategorized" else cat

    def activate(self, current_category: str = ""):
        """Activate the category header bar with current note's category."""
        clean = (current_category or "").strip()
        if clean.lower() == "uncategorized":
            clean = ""
        self._just_activated = True
        self.set_category(clean)
        self.entry.grab_focus()
        self.entry.select_region(0, -1)
        GLib.idle_add(self._show_all_suggestions)

    def _show_all_suggestions(self, _retried: bool = False):
        """Display the suggestions popover with all categories and keep text selected."""
        if not self._can_show_suggestions():
            # A freshly shown header page may not be mapped yet; retry once on the
            # next idle cycle, but never popup without a toplevel.
            if not _retried and self.get_root() is not None:
                GLib.idle_add(self._show_all_suggestions, True)
            return False
        self._populate_suggestions(show_all=True)
        self._update_popover_width()
        self._popup_suggestions()
        self.entry.grab_focus()
        self.entry.select_region(0, -1)
        return False

    def _show_completion_popup(self):
        """Compatibility helper to show all suggestions."""
        return self._show_all_suggestions()

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.suggestions_popover.popdown()
            self.emit("abort")
            return Gdk.EVENT_STOP
        elif keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            if not self.suggestions_popover.get_visible():
                self._populate_suggestions(show_all=self._is_text_fully_selected())
                self._update_popover_width()
                self._popup_suggestions()
            first = self.categories_listbox.get_first_child()
            if first:
                self.categories_listbox.select_row(first)
                first.grab_focus()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def _on_listbox_key_pressed(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.suggestions_popover.popdown()
            self.entry.grab_focus()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def _on_apply(self):
        self.suggestions_popover.popdown()
        new_category = self.entry.get_text().strip()
        if new_category.lower() == "uncategorized":
            new_category = ""
        self.emit("category-changed", new_category)

    def _on_clear(self):
        self.suggestions_popover.popdown()
        self.entry.set_text("")
        self.emit("category-changed", "")

# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Dict
from gi.repository import Adw, Gtk, GObject, Gio

class Sidebar(Gtk.Box):
    __gtype_name__ = "Sidebar"

    __gsignals__ = {
        "filter-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.active_filter_type = "all"
        self.active_category_name = ""

        self.add_css_class("stilo-sidebar")
        self.set_size_request(240, -1)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # HeaderBar for Sidebar
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_show_end_title_buttons(False)
        self.header_bar.set_show_start_title_buttons(False)

        title_lbl = Gtk.Label(label="Folders")
        title_lbl.add_css_class("heading")
        self.header_bar.set_title_widget(title_lbl)

        # Add Category Button
        add_cat_btn = Gtk.Button()
        add_cat_btn.set_icon_name("folder-new-symbolic")
        add_cat_btn.set_tooltip_text("New Category")
        add_cat_btn.connect("clicked", self._on_add_category_clicked)
        self.header_bar.pack_end(add_cat_btn)

        self.append(self.header_bar)

        # ScrolledWindow with ListBox
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class("navigation-sidebar")
        self.listbox.connect("row-selected", self._on_row_selected)

        scrolled.set_child(self.listbox)
        self.append(scrolled)

    def refresh(self):
        """Reload categories and counts."""
        # Clear existing rows
        while True:
            row = self.listbox.get_row_at_index(0)
            if not row:
                break
            self.listbox.remove(row)

        counts = self.db.get_counts()

        # 1. Standard Filters
        self._add_row("all", "", "All Notes", "document-edit-symbolic", counts.get("all", 0))
        self._add_row("pinned", "", "Favorites", "starred-symbolic", counts.get("pinned", 0))
        self._add_row("todo", "", "Tasks", "view-list-bullet-symbolic", counts.get("todo", 0))

        # 2. Categories
        categories = self.db.get_categories()
        if categories:
            # Separator / Header
            sep_row = Gtk.ListBoxRow()
            sep_row.set_selectable(False)
            sep_row.set_activatable(False)
            sep_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            sep_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
            cat_label = Gtk.Label(label="CATEGORIES")
            cat_label.set_halign(Gtk.Align.START)
            cat_label.add_css_class("dim-label")
            cat_label.add_css_class("caption")
            cat_label.set_margin_start(12)
            cat_label.set_margin_top(8)
            cat_label.set_margin_bottom(4)
            sep_box.append(cat_label)
            sep_row.set_child(sep_box)
            self.listbox.append(sep_row)

            for cat in categories:
                self._add_row("category", cat.name, cat.name, cat.icon or "folder-symbolic", cat.count, can_delete=True)

        # 3. Trash Section
        trash_sep = Gtk.ListBoxRow()
        trash_sep.set_selectable(False)
        trash_sep.set_activatable(False)
        trash_sep.set_child(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.listbox.append(trash_sep)

        self._add_row("trash", "", "Trash", "user-trash-symbolic", counts.get("trash", 0))

        # Re-select active filter
        self._restore_active_selection()

    def _add_row(self, filter_type: str, category_name: str, title: str, icon_name: str, count: int, can_delete: bool = False):
        row = Gtk.ListBoxRow()
        row.add_css_class("stilo-sidebar-row")
        row._filter_type = filter_type
        row._category_name = category_name

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        img = Gtk.Image.new_from_icon_name(icon_name)
        box.append(img)

        label = Gtk.Label(label=title)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        box.append(label)

        if count > 0:
            badge = Gtk.Label(label=str(count))
            badge.add_css_class("stilo-sidebar-badge")
            box.append(badge)

        if can_delete:
            del_btn = Gtk.Button()
            del_btn.set_icon_name("user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("circular")
            del_btn.set_tooltip_text(f"Delete category '{category_name}'")
            del_btn.connect("clicked", lambda _b, name=category_name: self._on_delete_category(name))
            box.append(del_btn)

        row.set_child(box)
        self.listbox.append(row)

    def _restore_active_selection(self):
        for i in range(100):
            row = self.listbox.get_row_at_index(i)
            if not row:
                break
            if getattr(row, "_filter_type", None) == self.active_filter_type and getattr(row, "_category_name", None) == self.active_category_name:
                self.listbox.select_row(row)
                break

    def _on_row_selected(self, _lb, row):
        if not row or not hasattr(row, "_filter_type"):
            return
        self.active_filter_type = row._filter_type
        self.active_category_name = row._category_name
        self.emit("filter-changed", self.active_filter_type, self.active_category_name)

    def _on_add_category_clicked(self, _btn):
        dialog = Adw.MessageDialog(
            heading="New Category",
            body="Enter a name for the new category:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. Work, Ideas, Journal")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "create":
                name = entry.get_text().strip()
                if name:
                    self.db.create_category(name)
                    self.refresh()
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.set_default_response("create")
        root_win = self.get_root()
        dialog.present(root_win)

    def _on_delete_category(self, name: str):
        dialog = Adw.MessageDialog(
            heading=f"Delete Category '{name}'?",
            body="Notes inside this category will remain, but their category will be cleared."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_d, response):
            if response == "delete":
                self.db.delete_category(name)
                if self.active_category_name == name:
                    self.active_filter_type = "all"
                    self.active_category_name = ""
                self.refresh()
            dialog.destroy()

        dialog.connect("response", on_response)
        root_win = self.get_root()
        dialog.present(root_win)

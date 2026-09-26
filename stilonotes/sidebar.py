# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject, Pango

from stilonotes.database import NoteDatabase


class Sidebar(Adw.Bin):
    __gtype_name__ = "Sidebar"

    __gsignals__ = {
        "filter-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "close-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db: NoteDatabase):
        super().__init__()
        self.db = db
        self.active_filter_type = "all"
        self.active_category_name = ""
        self._updating = False

        self.set_size_request(240, -1)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.toolbar_view = Adw.ToolbarView()

        # HeaderBar for Sidebar
        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_show_end_title_buttons(False)
        self.header_bar.set_show_start_title_buttons(False)

        # Close button (visible on mobile / overlay)
        self.close_btn = Gtk.Button()
        self.close_btn.set_icon_name("go-previous-symbolic")
        self.close_btn.set_tooltip_text("Close Categories")
        self.close_btn.connect("clicked", lambda _b: self.emit("close-requested"))
        self.close_btn.set_visible(False)
        self.header_bar.pack_start(self.close_btn)

        # Centered Window Title
        self.window_title = Adw.WindowTitle(title="Categories")
        self.header_bar.set_title_widget(self.window_title)

        # Add Category button
        self.add_cat_btn = Gtk.Button()
        self.add_cat_btn.set_icon_name("folder-new-symbolic")
        self.add_cat_btn.set_tooltip_text("New Category")
        self.add_cat_btn.connect("clicked", self._on_add_category_clicked)
        self.header_bar.pack_end(self.add_cat_btn)

        # Main Menu button (visible when pinned / desktop)
        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.set_tooltip_text("Main Menu")
        self.menu_btn.set_menu_model(self._create_main_menu())
        self.header_bar.pack_end(self.menu_btn)

        self.toolbar_view.add_top_bar(self.header_bar)

        # ScrolledWindow with navigation-sidebar ListBox
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.add_css_class("navigation-sidebar")
        self.listbox.connect("row-activated", self._on_row_activated)

        scrolled.set_child(self.listbox)
        self.toolbar_view.set_content(scrolled)

        self.set_child(self.toolbar_view)

    def _create_main_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append("About Stilo Notes", "app.about")
        return menu

    def show_buttons(self, show_close: bool, show_menu: bool):
        """Toggle close button vs main menu button based on sidebar pin / responsive mode."""
        self.close_btn.set_visible(show_close)
        self.menu_btn.set_visible(show_menu)

    def refresh(self):
        """Reload categories and counts."""
        self._updating = True
        try:
            # Clear existing rows
            while True:
                row = self.listbox.get_row_at_index(0)
                if not row:
                    break
                self.listbox.remove(row)

            counts = self.db.get_counts()

            # 1. All Notes
            self._add_row("all", "", "All Notes", "view-grid-symbolic", counts.get("all", 0))

            # 2. Uncategorized
            self._add_row("uncategorized", "", "Uncategorized", "view-grid-symbolic", counts.get("uncategorized", 0))

            # 3. Categories
            categories = self.db.get_categories()
            for cat in categories:
                self._add_row("category", cat.name, cat.name, cat.icon or "folder-symbolic", cat.count, is_user_category=True)

            # 4. Trash
            self._add_row("trash", "", "Trash", "user-trash-symbolic", counts.get("trash", 0))

            # Re-select active filter
            self._restore_active_selection()
        finally:
            self._updating = False

    def _add_row(self, filter_type: str, category_name: str, title: str, icon_name: str, count: int, is_user_category: bool = False):
        row = Gtk.ListBoxRow()
        row._filter_type = filter_type
        row._category_name = category_name

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(16)
        img.add_css_class("dimmed")
        box.append(img)

        label = Gtk.Label(label=title)
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0.0)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        box.append(label)

        if count > 0:
            count_lbl = Gtk.Label(label=str(count))
            count_lbl.add_css_class("caption")
            count_lbl.add_css_class("dimmed")
            count_lbl.set_margin_end(4)
            box.append(count_lbl)

        if is_user_category:
            self._setup_category_context_menu(row, category_name)

        row.set_child(box)
        self.listbox.append(row)

    def _setup_category_context_menu(self, row: Gtk.ListBoxRow, category_name: str):
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)  # Right click

        def on_right_click(_g, _n, _x, _y):
            menu = Gio.Menu()
            menu.append("Rename Category", f"cat.rename::{category_name}")
            menu.append("Delete Category", f"cat.delete::{category_name}")

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(row)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup.new()

            act_rename = Gio.SimpleAction.new("rename", GLib.VariantType.new("s"))
            act_rename.connect("activate", lambda _a, p: self._on_rename_category(p.get_string()))
            action_group.add_action(act_rename)

            act_del = Gio.SimpleAction.new("delete", GLib.VariantType.new("s"))
            act_del.connect("activate", lambda _a, p: self._on_delete_category(p.get_string()))
            action_group.add_action(act_del)

            row.insert_action_group("cat", action_group)
            popover.popup()

        gesture.connect("pressed", on_right_click)
        row.add_controller(gesture)

    def _restore_active_selection(self):
        for i in range(100):
            row = self.listbox.get_row_at_index(i)
            if not row:
                break
            if getattr(row, "_filter_type", None) == self.active_filter_type and getattr(row, "_category_name", None) == self.active_category_name:
                self.listbox.select_row(row)
                break

    def _on_row_activated(self, _lb, row):
        if self._updating or not row or not hasattr(row, "_filter_type"):
            return
        if self.active_filter_type == row._filter_type and self.active_category_name == row._category_name:
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
        entry.set_placeholder_text("e.g. Ideas, Journal, Work")
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

    def _on_rename_category(self, old_name: str):
        dialog = Adw.MessageDialog(
            heading=f"Rename Category '{old_name}'",
            body="Enter a new name for this category:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)

        entry = Gtk.Entry()
        entry.set_text(old_name)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "rename":
                new_name = entry.get_text().strip()
                if new_name and new_name != old_name:
                    with self.db.get_connection() as conn:
                        conn.execute("UPDATE categories SET name = ? WHERE name = ?", (new_name, old_name))
                        conn.execute("UPDATE notes SET category = ? WHERE category = ?", (new_name, old_name))
                    if self.active_category_name == old_name:
                        self.active_category_name = new_name
                    self.refresh()
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.set_default_response("rename")
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

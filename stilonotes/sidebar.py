# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject, Pango

from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.theme_selector import ThemeSelector


def _build_category_tree(categories):
    """
    Given a flat list of Category objects whose names may contain '/' separators,
    return an ordered list of (full_name, depth, display_name, has_children) tuples that
    represents a depth-first tree walk.
    """
    # Build a prefix-tree from names
    tree = {}  # node: {child_name: subtree}
    for cat in categories:
        name = getattr(cat, "name", str(cat)).strip().strip("/")
        if not name:
            continue
        parts = [p.strip() for p in name.split("/") if p.strip()]
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    result = []

    def walk(node, prefix, depth):
        for key in sorted(node.keys()):
            full = f"{prefix}/{key}" if prefix else key
            has_children = len(node[key]) > 0
            result.append((full, depth, key, has_children))
            walk(node[key], full, depth + 1)

    walk(tree, "", 0)
    return result


class Sidebar(Adw.Bin):
    __gtype_name__ = "Sidebar"

    __gsignals__ = {
        "filter-changed":  (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "close-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db: NoteDatabase):
        super().__init__()
        self.db = db
        self.config_manager = ConfigManager.get_default(self.db)
        self.active_filter_type = "all"
        self.active_category_name = ""
        self._updating = False
        self._toggling_category = False
        self._collapsed_categories = set(self.config_manager.get_collapsed_categories())
        self._category_rows = {}

        self.set_size_request(240, -1)
        self._build_ui()
        self.refresh()

    def _is_category_visible(self, category_name: str) -> bool:
        """A category is visible if none of its ancestor categories are collapsed."""
        parts = category_name.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor in self._collapsed_categories:
                return False
        return True

    def _ensure_ancestors_expanded(self, category_name: str) -> bool:
        """Ensure all ancestor categories of category_name are expanded."""
        parts = category_name.split("/")
        changed = False
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor in self._collapsed_categories:
                self._collapsed_categories.remove(ancestor)
                changed = True
        if changed:
            self.config_manager.set_collapsed_categories(self._collapsed_categories)
        return changed

    def _build_ui(self):
        self.toolbar_view = Adw.ToolbarView()

        self.header_bar = Adw.HeaderBar()
        self.header_bar.set_show_end_title_buttons(False)
        self.header_bar.set_show_start_title_buttons(False)

        self.close_btn = Gtk.Button()
        self.close_btn.set_icon_name("go-previous-symbolic")
        self.close_btn.set_tooltip_text("Close Categories")
        self.close_btn.connect("clicked", lambda _b: self.emit("close-requested"))
        self.close_btn.set_visible(False)
        self.header_bar.pack_start(self.close_btn)

        self.add_cat_btn = Gtk.Button()
        self.add_cat_btn.set_icon_name("folder-new-symbolic")
        self.add_cat_btn.set_tooltip_text("New Category (use / for nested, e.g. Work/Projects)")
        self.add_cat_btn.connect("clicked", self._on_add_category_clicked)
        self.header_bar.pack_start(self.add_cat_btn)

        self.window_title = Adw.WindowTitle(title="Categories & Tags")
        self.header_bar.set_title_widget(self.window_title)

        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.set_icon_name("open-menu-symbolic")
        self.menu_btn.set_tooltip_text("Main Menu")
        self.menu_btn.set_menu_model(self._create_main_menu())
        self.theme_selector = ThemeSelector(self.config_manager)
        self.menu_btn.get_popover().add_child(self.theme_selector, "theme")
        self.header_bar.pack_end(self.menu_btn)

        self.toolbar_view.add_top_bar(self.header_bar)

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
        s_theme = Gio.Menu()
        item_theme = Gio.MenuItem.new(None, None)
        item_theme.set_attribute_value("custom", GLib.Variant.new_string("theme"))
        s_theme.append_item(item_theme)
        menu.append_section(None, s_theme)

        s_app = Gio.Menu()
        s_app.append("Preferences",       "app.preferences")
        s_app.append("Keyboard Shortcuts","app.shortcuts")
        s_app.append("About Stilo Notes", "app.about")
        menu.append_section(None, s_app)
        return menu

    def show_buttons(self, show_close: bool, show_menu: bool):
        self.close_btn.set_visible(show_close)
        self.menu_btn.set_visible(show_menu)

    def refresh(self):
        """Reload categories and counts."""
        self._updating = True
        try:
            self.listbox.remove_all()
            self._category_rows.clear()

            counts = self.db.get_counts()

            # 1. All Notes
            self._add_row("all", "", "All Notes", "view-grid-symbolic", counts.get("all", 0))

            # 2. Favorites (pinned)
            fav_count = counts.get("favorites", 0)
            self._add_row("favorites", "", "Favorites", "starred-symbolic", fav_count)

            # 3. Uncategorized
            self._add_row("uncategorized", "", "Uncategorized", "folder-open-symbolic",
                          counts.get("uncategorized", 0))

            # 4. Nested categories tree
            categories = self.db.get_categories()
            tree_items = _build_category_tree(categories)
            if tree_items:
                if self.active_filter_type == "category" and self.active_category_name:
                    self._ensure_ancestors_expanded(self.active_category_name)

                self._add_section_header("Categories", "folder-symbolic")
                for full_name, depth, display_name, has_children in tree_items:
                    icon = "folder-symbolic" if depth == 0 else "folder-open-symbolic"
                    is_expanded = full_name not in self._collapsed_categories
                    self._add_row(
                        "category", full_name, display_name, icon,
                        counts.get(f"cat:{full_name}", 0),
                        is_user_category=True,
                        depth=depth,
                        has_children=has_children,
                        is_expanded=is_expanded
                    )

            # 5. Tags section
            tags = self.db.get_all_tags()
            if tags:
                self._add_section_header("Tags", "tag-symbolic")
                for tag_name, cnt in tags:
                    self._add_row("tag", tag_name, f"#{tag_name}", "tag-symbolic", cnt)

            # 6. Trash
            self._add_row("trash", "", "Trash", "user-trash-symbolic", counts.get("trash", 0))

            self._restore_active_selection()
        finally:
            self._updating = False

    def _add_section_header(self, title: str, icon_name: str = ""):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_can_focus(False)
        row.add_css_class("sidebar-section-header")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(12)
        box.set_margin_bottom(4)

        if icon_name:
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(13)
            img.add_css_class("dim-label")
            box.append(img)

        lbl = Gtk.Label(label=title)
        lbl.add_css_class("caption-heading")
        lbl.add_css_class("dim-label")
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        row.set_child(box)
        self.listbox.append(row)

    def _add_row(
        self, filter_type: str, category_name: str, title: str,
        icon_name: str, count: int, is_user_category: bool = False, depth: int = 0,
        has_children: bool = False, is_expanded: bool = True
    ):
        row = Gtk.ListBoxRow()
        row._filter_type = filter_type
        row._category_name = category_name
        row._has_children = has_children
        row._depth = depth

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        # Indent nested categories
        box.set_margin_start(10 + depth * 16)
        box.set_margin_end(10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        if is_user_category:
            self._category_rows[category_name] = row
            is_visible = self._is_category_visible(category_name)
            row.set_visible(is_visible)

            if has_children:
                arrow_btn = Gtk.Button()
                arrow_btn.set_has_frame(False)
                arrow_btn.add_css_class("flat")
                arrow_btn.add_css_class("category-expander")
                arrow_btn.set_valign(Gtk.Align.CENTER)
                arrow_btn.set_halign(Gtk.Align.CENTER)
                arrow_btn.set_can_focus(False)
                arrow_btn.set_tooltip_text("Collapse" if is_expanded else "Expand")

                arrow_img = Gtk.Image.new_from_icon_name(
                    "pan-down-symbolic" if is_expanded else "pan-end-symbolic"
                )
                arrow_img.set_pixel_size(12)
                arrow_btn.set_child(arrow_img)
                arrow_btn.connect("clicked", lambda _b, cat=category_name: self._on_toggle_category(cat))

                row._arrow_btn = arrow_btn
                row._arrow_img = arrow_img
                box.append(arrow_btn)
            else:
                spacer = Gtk.Box()
                spacer.set_size_request(18, -1)
                box.append(spacer)

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
        gesture.set_button(3)

        def on_right_click(_g, _n, _x, _y):
            menu = Gio.Menu()
            s1 = Gio.Menu()
            s1.append("Add Subcategory…", f"cat.add-sub::{category_name}")
            s1.append("Rename Category…", f"cat.rename::{category_name}")
            menu.append_section(None, s1)
            s2 = Gio.Menu()
            s2.append("Delete Category",  f"cat.delete::{category_name}")
            menu.append_section(None, s2)

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(row)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup.new()

            act_sub = Gio.SimpleAction.new("add-sub", GLib.VariantType.new("s"))
            act_sub.connect("activate", lambda _a, p: self._on_add_subcategory(p.get_string()))
            action_group.add_action(act_sub)

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

    def _on_toggle_category(self, cat_name: str):
        self._toggling_category = True
        try:
            if cat_name in self._collapsed_categories:
                self._collapsed_categories.remove(cat_name)
            else:
                self._collapsed_categories.add(cat_name)
                # If currently selected category was inside this newly collapsed category,
                # move selection to the parent category so it remains visible
                if (self.active_filter_type == "category" and
                        self.active_category_name.startswith(cat_name + "/")):
                    self.active_category_name = cat_name
                    self.emit("filter-changed", "category", cat_name)

            self.config_manager.set_collapsed_categories(self._collapsed_categories)
            self._update_category_tree_ui()
        finally:
            GLib.idle_add(self._clear_toggling_flag)

    def _clear_toggling_flag(self):
        self._toggling_category = False
        return GLib.SOURCE_REMOVE

    def _update_category_tree_ui(self):
        for name, row in self._category_rows.items():
            row.set_visible(self._is_category_visible(name))

            if hasattr(row, "_arrow_img") and hasattr(row, "_arrow_btn"):
                is_collapsed = name in self._collapsed_categories
                icon_name = "pan-end-symbolic" if is_collapsed else "pan-down-symbolic"
                row._arrow_img.set_from_icon_name(icon_name)
                row._arrow_btn.set_tooltip_text("Expand" if is_collapsed else "Collapse")

        self._restore_active_selection()

    def _restore_active_selection(self):
        for i in range(300):
            row = self.listbox.get_row_at_index(i)
            if not row:
                break
            if (getattr(row, "_filter_type", None) == self.active_filter_type and
                    getattr(row, "_category_name", None) == self.active_category_name):
                self.listbox.select_row(row)
                break

    def _on_row_activated(self, _lb, row):
        if self._updating or self._toggling_category or not row or not hasattr(row, "_filter_type"):
            return
        if (self.active_filter_type == row._filter_type and
                self.active_category_name == row._category_name):
            return
        self.active_filter_type = row._filter_type
        self.active_category_name = row._category_name
        self.emit("filter-changed", self.active_filter_type, self.active_category_name)

    # ── Add category dialog ───────────────────────────────────────────────

    def _on_add_category_clicked(self, _btn):
        dialog = Adw.AlertDialog.new(
            "New Category",
            "Enter a name. Use / for nested categories (e.g. Work/Projects):"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. Ideas  or  Work/Projects")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "create":
                name = entry.get_text().strip().strip("/")
                if name:
                    self._create_category_with_parents(name)
                    # Expand ancestor categories so new category is visible
                    parts = name.split("/")
                    for i in range(1, len(parts)):
                        self._collapsed_categories.discard("/".join(parts[:i]))
                    self.config_manager.set_collapsed_categories(self._collapsed_categories)
                    self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    def _on_add_subcategory(self, parent_name: str):
        dialog = Adw.AlertDialog.new(
            f"New Subcategory under '{parent_name}'",
            "Enter the subcategory name:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. Reports")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "create":
                sub = entry.get_text().strip().strip("/")
                if sub:
                    full = f"{parent_name}/{sub}"
                    self._create_category_with_parents(full)
                    # Expand parent and its ancestors so new subcategory is visible
                    parts = full.split("/")
                    for i in range(1, len(parts)):
                        self._collapsed_categories.discard("/".join(parts[:i]))
                    self.config_manager.set_collapsed_categories(self._collapsed_categories)
                    self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    def _create_category_with_parents(self, full_name: str):
        """Create a category and any missing ancestor categories."""
        parts = full_name.split("/")
        for i in range(len(parts)):
            ancestor = "/".join(parts[:i + 1])
            self.db.create_category(ancestor)

    # ── Rename dialog ─────────────────────────────────────────────────────

    def _on_rename_category(self, old_name: str):
        dialog = Adw.AlertDialog.new(
            f"Rename '{old_name}'",
            "Enter a new name:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_text(old_name)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "rename":
                new_name = entry.get_text().strip().strip("/")
                if new_name and new_name != old_name:
                    self.db.rename_category(old_name, new_name)
                    if self.active_category_name == old_name:
                        self.active_category_name = new_name
                    elif self.active_category_name.startswith(old_name + "/"):
                        self.active_category_name = new_name + self.active_category_name[len(old_name):]

                    # Update collapsed categories
                    new_collapsed = set()
                    for cat in self._collapsed_categories:
                        if cat == old_name:
                            new_collapsed.add(new_name)
                        elif cat.startswith(old_name + "/"):
                            new_collapsed.add(new_name + cat[len(old_name):])
                        else:
                            new_collapsed.add(cat)
                    self._collapsed_categories = new_collapsed
                    self.config_manager.set_collapsed_categories(self._collapsed_categories)

                    self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    # ── Delete dialog ─────────────────────────────────────────────────────

    def _on_delete_category(self, name: str):
        dialog = Adw.AlertDialog.new(
            f"Delete '{name}'?",
            "Notes inside will remain but their category will be cleared.\n"
            "All subcategories will also be deleted."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response):
            if response == "delete":
                self.db.delete_category(name)
                if self.active_category_name == name or self.active_category_name.startswith(name + "/"):
                    self.active_filter_type = "all"
                    self.active_category_name = ""

                # Clean up collapsed categories
                self._collapsed_categories = {
                    cat for cat in self._collapsed_categories
                    if cat != name and not cat.startswith(name + "/")
                }
                self.config_manager.set_collapsed_categories(self._collapsed_categories)

                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

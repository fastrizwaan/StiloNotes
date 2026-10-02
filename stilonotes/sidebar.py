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
        "width-dragged":   (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "width-drag-ended": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
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
        self._categories_expanded = self.config_manager.get_categories_expanded()
        self._tags_expanded = self.config_manager.get_tags_expanded()
        self._category_rows = {}
        self._tag_rows = {}
        self._drag_start_width = self.config_manager.get_sidebar_width()
        self._last_emitted_width = self._drag_start_width
        self._mouse_edge_offset: Optional[float] = None

        self.set_size_request(200, -1)
        self.add_css_class("sidebar-view")
        self._build_ui()
        self.refresh()

    def _is_category_visible(self, category_name: str) -> bool:
        """A category is visible if categories section is expanded and none of its ancestors are collapsed."""
        if not self._categories_expanded:
            return False
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
        self.add_cat_btn.set_visible(False)
        self.header_bar.pack_start(self.add_cat_btn)

        self.window_title = Adw.WindowTitle(title="Stilo Notes")
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
        scrolled.add_css_class("sidebar-scrolled-window")
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

        # Outer layout: ToolbarView + draggable vertical resizer handle
        outer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        outer_box.set_hexpand(True)
        outer_box.set_vexpand(True)

        self.toolbar_view.set_hexpand(True)
        outer_box.append(self.toolbar_view)

        self.drag_handle = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.drag_handle.add_css_class("sidebar-resizer")
        self.drag_handle.set_size_request(5, -1)
        self.drag_handle.set_vexpand(True)
        try:
            from gi.repository import Gdk
            self.drag_handle.set_cursor(Gdk.Cursor.new_from_name("col-resize", None))
        except Exception:
            pass

        drag_gesture = Gtk.GestureDrag.new()
        drag_gesture.connect("drag-begin", self._on_resizer_drag_begin)
        drag_gesture.connect("drag-update", self._on_resizer_drag_update)
        drag_gesture.connect("drag-end", self._on_resizer_drag_end)
        self.drag_handle.add_controller(drag_gesture)

        outer_box.append(self.drag_handle)
        self.set_child(outer_box)

    def _get_event_surface_x(self, gesture) -> Optional[float]:
        try:
            seq = gesture.get_current_sequence()
            ev = gesture.get_last_event(seq)
            if not ev:
                ev = gesture.get_current_event()
            if ev:
                ok, x, _y = ev.get_position()
                if ok:
                    return float(x)
        except Exception:
            pass
        return None

    def _on_resizer_drag_begin(self, gesture, start_x, start_y):
        self._drag_start_width = self.get_width()
        if self._drag_start_width <= 0:
            self._drag_start_width = self.config_manager.get_sidebar_width()
        self.drag_handle.add_css_class("dragging")
        self._last_emitted_width = self._drag_start_width

        start_surface_x = self._get_event_surface_x(gesture)
        if start_surface_x is not None:
            is_rtl = (self.get_direction() == Gtk.TextDirection.RTL)
            if is_rtl and self.get_root():
                win_w = float(self.get_root().get_width())
                self._mouse_edge_offset = float(self._drag_start_width) - (win_w - start_surface_x)
            else:
                self._mouse_edge_offset = float(self._drag_start_width) - start_surface_x
        else:
            self._mouse_edge_offset = None

    def _calculate_target_width(self, gesture, offset_x: float) -> int:
        cur_surface_x = self._get_event_surface_x(gesture)
        if cur_surface_x is not None and self._mouse_edge_offset is not None:
            is_rtl = (self.get_direction() == Gtk.TextDirection.RTL)
            if is_rtl and self.get_root():
                win_w = float(self.get_root().get_width())
                target_w = (win_w - cur_surface_x) + self._mouse_edge_offset
            else:
                target_w = cur_surface_x + self._mouse_edge_offset
            return max(200, min(int(round(target_w)), 500))
        return max(200, min(int(self._drag_start_width + offset_x), 500))

    def _on_resizer_drag_update(self, gesture, offset_x, offset_y):
        new_width = self._calculate_target_width(gesture, offset_x)
        if new_width != self._last_emitted_width:
            self._last_emitted_width = new_width
            self.emit("width-dragged", new_width)

    def _on_resizer_drag_end(self, gesture, offset_x, offset_y):
        self.drag_handle.remove_css_class("dragging")
        final_width = self._calculate_target_width(gesture, offset_x)
        self._last_emitted_width = final_width
        self.config_manager.set_sidebar_width(final_width)
        self.emit("width-dragged", final_width)
        self.emit("width-drag-ended", final_width)

    def set_resizer_visible(self, visible: bool):
        if hasattr(self, "drag_handle"):
            self.drag_handle.set_visible(visible)

    def _create_main_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        s_theme = Gio.Menu()
        item_theme = Gio.MenuItem.new(None, None)
        item_theme.set_attribute_value("custom", GLib.Variant.new_string("theme"))
        s_theme.append_item(item_theme)
        menu.append_section(None, s_theme)

        s_window = Gio.Menu()
        s_window.append("New Window", "app.new-window")
        menu.append_section(None, s_window)

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
            self._tag_rows.clear()

            counts = self.db.get_counts()

            # 1. Standard navigation items
            self._add_row("all", "", "All Notes", "view-grid-symbolic", counts.get("all", 0))
            fav_count = counts.get("favorites", counts.get("pinned", 0))
            self._add_row("favorites", "", "Favorites", "starred-symbolic", fav_count)
            todo_count = counts.get("todos", counts.get("todo", 0))
            self._add_row("todos", "", "Todos", "checkbox-checked-symbolic", todo_count)
            list_count = counts.get("lists", counts.get("list", 0))
            self._add_row("lists", "", "Lists", "view-list-bullet-symbolic", list_count)
            recent_count = counts.get("recent", 0)
            self._add_row("recent", "", "Recent", "document-open-recent-symbolic", recent_count)
            self._add_row("uncategorized", "", "Uncategorized", "folder-open-symbolic",
                          counts.get("uncategorized", 0))

            # 2. Categories section
            self._add_separator()
            self._add_categories_header_row()

            categories = self.db.get_categories()
            tree_items = _build_category_tree(categories)
            if tree_items:
                if self.active_filter_type == "category" and self.active_category_name:
                    self._ensure_ancestors_expanded(self.active_category_name)

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

            # 3. Tags section
            self._add_separator()
            self._add_tags_header_row()

            tags = self.db.get_all_tags()
            if tags:
                for tag_name, cnt in tags:
                    self._add_row("tag", tag_name, f"#{tag_name}", "tag-symbolic", cnt, is_tag=True)

            # 4. Trash
            self._add_separator()
            self._add_row("trash", "", "Trash", "user-trash-symbolic", counts.get("trash", 0))

            self._restore_active_selection()
        finally:
            self._updating = False

    def _add_separator(self):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_can_focus(False)
        row.add_css_class("sidebar-separator-row")

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_hexpand(True)
        sep.set_halign(Gtk.Align.FILL)
        row.set_child(sep)
        self.listbox.append(row)

    def _add_categories_header_row(self):
        row = Gtk.ListBoxRow()
        row._filter_type = "categories_header"
        row._category_name = ""
        row.set_selectable(False)
        row.set_activatable(True)
        row.add_css_class("sidebar-section-header-row")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(0)
        box.set_margin_end(0)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        img = Gtk.Image.new_from_icon_name("folder-symbolic")
        img.set_pixel_size(16)
        img.add_css_class("dimmed")
        box.append(img)

        label = Gtk.Label(label="Categories")
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0.0)
        label.set_hexpand(True)
        label.add_css_class("section-title")
        box.append(label)

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        # + button
        add_btn = Gtk.Button()
        add_btn.set_tooltip_text("New Category")
        add_btn.set_has_frame(False)
        add_btn.add_css_class("flat")
        add_btn.add_css_class("sidebar-action-btn")
        add_btn.set_can_focus(False)
        add_img = Gtk.Image.new_from_icon_name("list-add-symbolic")
        add_img.set_pixel_size(14)
        add_btn.set_child(add_img)

        def on_add_cat_clicked(_b):
            self._toggling_category = True
            try:
                self._on_add_category_clicked(_b)
            finally:
                GLib.idle_add(self._clear_toggling_flag)
        add_btn.connect("clicked", on_add_cat_clicked)
        actions_box.append(add_btn)

        # > chevron button (only shown when collapsed)
        chevron_btn = Gtk.Button()
        chevron_btn.set_has_frame(False)
        chevron_btn.add_css_class("flat")
        chevron_btn.add_css_class("category-expander")
        chevron_btn.set_can_focus(False)
        chevron_btn.set_tooltip_text("Expand Categories")
        chevron_btn.set_visible(not self._categories_expanded)

        chevron_img = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        chevron_img.set_pixel_size(14)
        chevron_btn.set_child(chevron_img)

        def on_chevron_clicked(_b):
            self._toggling_category = True
            try:
                self._on_toggle_categories_section()
            finally:
                GLib.idle_add(self._clear_toggling_flag)
        chevron_btn.connect("clicked", on_chevron_clicked)
        actions_box.append(chevron_btn)

        self._categories_chevron_btn = chevron_btn
        self._categories_chevron_img = chevron_img

        box.append(actions_box)
        row.set_child(box)
        self.listbox.append(row)

    def _add_tags_header_row(self):
        row = Gtk.ListBoxRow()
        row._filter_type = "tags_header"
        row._category_name = ""
        row.set_selectable(False)
        row.set_activatable(True)
        row.add_css_class("sidebar-section-header-row")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(0)
        box.set_margin_end(0)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        img = Gtk.Image.new_from_icon_name("tag-symbolic")
        img.set_pixel_size(16)
        img.add_css_class("dimmed")
        box.append(img)

        label = Gtk.Label(label="Tags")
        label.set_halign(Gtk.Align.START)
        label.set_xalign(0.0)
        label.set_hexpand(True)
        label.add_css_class("section-title")
        box.append(label)

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        # + button with dropdown Popover
        add_tag_btn = Gtk.MenuButton()
        add_tag_btn.set_tooltip_text("Add Tag")
        add_tag_btn.set_has_frame(False)
        add_tag_btn.add_css_class("flat")
        add_tag_btn.add_css_class("sidebar-action-btn")
        add_tag_btn.set_can_focus(False)

        add_tag_img = Gtk.Image.new_from_icon_name("list-add-symbolic")
        add_tag_img.set_pixel_size(14)
        add_tag_btn.set_child(add_tag_img)

        popover = Gtk.Popover()
        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pop_box.set_margin_top(10)
        pop_box.set_margin_bottom(10)
        pop_box.set_margin_start(10)
        pop_box.set_margin_end(10)
        pop_box.set_size_request(200, -1)

        pop_title = Gtk.Label(label="New Tag")
        pop_title.add_css_class("heading")
        pop_title.set_halign(Gtk.Align.START)
        pop_box.append(pop_title)

        tag_entry = Gtk.Entry()
        tag_entry.set_placeholder_text("Tag name…")
        tag_entry.set_activates_default(True)
        pop_box.append(tag_entry)

        submit_btn = Gtk.Button(label="Add Tag")
        submit_btn.add_css_class("suggested-action")
        pop_box.append(submit_btn)

        def do_add_tag():
            val = tag_entry.get_text().strip().lstrip("#")
            if val:
                tag_entry.set_text("")
                self._on_add_tag_from_dropdown(val, popover)

        tag_entry.connect("activate", lambda _e: do_add_tag())
        submit_btn.connect("clicked", lambda _b: do_add_tag())

        popover.set_child(pop_box)
        add_tag_btn.set_popover(popover)
        actions_box.append(add_tag_btn)

        # > chevron button (only shown when collapsed)
        chevron_btn = Gtk.Button()
        chevron_btn.set_has_frame(False)
        chevron_btn.add_css_class("flat")
        chevron_btn.add_css_class("category-expander")
        chevron_btn.set_can_focus(False)
        chevron_btn.set_tooltip_text("Expand Tags")
        chevron_btn.set_visible(not self._tags_expanded)

        chevron_img = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        chevron_img.set_pixel_size(14)
        chevron_btn.set_child(chevron_img)

        def on_chevron_clicked(_b):
            self._toggling_category = True
            try:
                self._on_toggle_tags_section()
            finally:
                GLib.idle_add(self._clear_toggling_flag)
        chevron_btn.connect("clicked", on_chevron_clicked)
        actions_box.append(chevron_btn)

        self._tags_chevron_btn = chevron_btn
        self._tags_chevron_img = chevron_img

        box.append(actions_box)
        row.set_child(box)
        self.listbox.append(row)

    def _on_add_tag_from_dropdown(self, tag_name: str, popover: Gtk.Popover):
        clean = tag_name.strip().lstrip("#").lower()
        if not clean:
            return
        popover.popdown()

        root = self.get_root()
        active_note_id = None
        if root and hasattr(root, "editor") and getattr(root.editor, "current_note", None):
            active_note_id = root.editor.current_note.id
        elif root and hasattr(root, "index_view") and hasattr(root.index_view, "notes_list"):
            selected_card = getattr(root.index_view.notes_list, "_selected_card", None)
            if selected_card and getattr(selected_card, "note", None):
                active_note_id = selected_card.note.id

        if active_note_id:
            note = self.db.get_note(active_note_id)
            if note:
                cur_tags = note.tags or []
                if clean not in cur_tags:
                    new_tags = list(dict.fromkeys(cur_tags + [clean]))
                    self.db.save_note(active_note_id, tags=new_tags)
                    if root and hasattr(root, "editor") and getattr(root.editor, "current_note", None):
                        if root.editor.current_note.id == active_note_id:
                            root.editor.current_note.tags = new_tags
        else:
            new_note = self.db.create_note(title="Untitled Note", tags=[clean])
            if root and hasattr(root, "_on_note_opened"):
                root._on_note_opened(None, new_note, False)

        self._tags_expanded = True
        self.config_manager.set_tags_expanded(True)
        self.refresh()
        self.active_filter_type = "tag"
        self.active_category_name = clean
        self.emit("filter-changed", "tag", clean)

    def _on_toggle_categories_section(self):
        self._categories_expanded = not self._categories_expanded
        self.config_manager.set_categories_expanded(self._categories_expanded)
        if hasattr(self, "_categories_chevron_btn"):
            self._categories_chevron_btn.set_visible(not self._categories_expanded)
        self._update_category_tree_ui()

    def _on_toggle_tags_section(self):
        self._tags_expanded = not self._tags_expanded
        self.config_manager.set_tags_expanded(self._tags_expanded)
        if hasattr(self, "_tags_chevron_btn"):
            self._tags_chevron_btn.set_visible(not self._tags_expanded)
        for tag_name, row in self._tag_rows.items():
            row.set_visible(self._tags_expanded)

    def _add_row(
        self, filter_type: str, category_name: str, title: str,
        icon_name: str, count: int, is_user_category: bool = False, depth: int = 0,
        has_children: bool = False, is_expanded: bool = True, is_tag: bool = False
    ):
        row = Gtk.ListBoxRow()
        row._filter_type = filter_type
        row._category_name = category_name
        row._has_children = has_children
        row._depth = depth

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # Depth 0: margin-start is 0 (aligns left with Categories, not indented)
        # Depth 1+: indented by 16px per depth level to show hierarchy
        if is_user_category:
            box.set_margin_start(depth * 16)
        else:
            box.set_margin_start(0)
        box.set_margin_end(0)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

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
            count_lbl.set_margin_end(2)
            box.append(count_lbl)

        if is_user_category:
            self._category_rows[category_name] = row
            is_visible = self._is_category_visible(category_name)
            row.set_visible(is_visible)

            # AdwExpanderRow style: expander chevron on the right side
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
                arrow_img.set_pixel_size(14)
                arrow_btn.set_child(arrow_img)
                arrow_btn.connect("clicked", lambda _b, cat=category_name: self._on_toggle_category(cat))

                row._arrow_btn = arrow_btn
                row._arrow_img = arrow_img
                box.append(arrow_btn)

            self._setup_category_context_menu(row, category_name)

        if is_tag:
            self._tag_rows[category_name] = row
            row.set_visible(self._tags_expanded)
            self._setup_tag_context_menu(row, category_name)

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

    def _setup_tag_context_menu(self, row: Gtk.ListBoxRow, tag_name: str):
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)

        def on_right_click(_g, _n, _x, _y):
            menu = Gio.Menu()
            s1 = Gio.Menu()
            s1.append("Rename Tag…", f"tag.rename::{tag_name}")
            menu.append_section(None, s1)
            s2 = Gio.Menu()
            s2.append("Delete Tag", f"tag.delete::{tag_name}")
            menu.append_section(None, s2)

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(row)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup.new()

            act_rename = Gio.SimpleAction.new("rename", GLib.VariantType.new("s"))
            act_rename.connect("activate", lambda _a, p: self._on_rename_tag(p.get_string()))
            action_group.add_action(act_rename)

            act_del = Gio.SimpleAction.new("delete", GLib.VariantType.new("s"))
            act_del.connect("activate", lambda _a, p: self._on_delete_tag(p.get_string()))
            action_group.add_action(act_del)

            row.insert_action_group("tag", action_group)
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
        if row._filter_type == "categories_header":
            self._on_toggle_categories_section()
            return
        if row._filter_type == "tags_header":
            self._on_toggle_tags_section()
            return
        if (self.active_filter_type == row._filter_type and
                self.active_category_name == row._category_name):
            if getattr(row, "_has_children", False):
                self._on_toggle_category(row._category_name)
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
                    self._categories_expanded = True
                    self.config_manager.set_categories_expanded(True)
                    self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    def _on_add_subcategory(self, parent_name: str):
        parent_display = parent_name.split("/")[-1]
        dialog = Adw.AlertDialog.new(
            f"New Subcategory under '{parent_display}'",
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
        display_name = old_name.split("/")[-1]
        dialog = Adw.AlertDialog.new(
            f"Rename '{display_name}'",
            "Enter a new name:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_text(display_name)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "rename":
                new_leaf = entry.get_text().strip().strip("/")
                if not new_leaf:
                    return

                if "/" in old_name:
                    parent_path = old_name.rsplit("/", 1)[0]
                    new_name = f"{parent_path}/{new_leaf}"
                else:
                    new_name = new_leaf

                if new_name != old_name:
                    self.db.rename_category(old_name, new_name)
                    was_active = False
                    if self.active_category_name == old_name:
                        self.active_category_name = new_name
                        was_active = True
                    elif self.active_category_name.startswith(old_name + "/"):
                        self.active_category_name = new_name + self.active_category_name[len(old_name):]
                        was_active = True

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
                    if was_active:
                        self.emit("filter-changed", "category", self.active_category_name)

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    # ── Delete dialog ─────────────────────────────────────────────────────

    def _on_delete_category(self, name: str):
        display_name = name.split("/")[-1]
        dialog = Adw.AlertDialog.new(
            f"Delete '{display_name}'?",
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
                was_active = False
                if self.active_category_name == name or self.active_category_name.startswith(name + "/"):
                    self.active_filter_type = "all"
                    self.active_category_name = ""
                    was_active = True

                # Clean up collapsed categories
                self._collapsed_categories = {
                    cat for cat in self._collapsed_categories
                    if cat != name and not cat.startswith(name + "/")
                }
                self.config_manager.set_collapsed_categories(self._collapsed_categories)

                self.refresh()
                if was_active:
                    self.emit("filter-changed", "all", "")

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    # ── Tag dialogs ────────────────────────────────────────────────────────

    def _on_rename_tag(self, old_tag: str):
        dialog = Adw.AlertDialog.new(
            f"Rename Tag '#{old_tag}'",
            "Enter a new tag name:"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_text(old_tag)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "rename":
                new_tag = entry.get_text().strip().lstrip("#").lower()
                if new_tag and new_tag != old_tag:
                    self.db.rename_tag(old_tag, new_tag)
                    if self.active_filter_type == "tag" and self.active_category_name == old_tag:
                        self.active_category_name = new_tag
                        self.emit("filter-changed", "tag", new_tag)
                    self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    def _on_delete_tag(self, tag_name: str):
        dialog = Adw.AlertDialog.new(
            f"Delete Tag '#{tag_name}'?",
            "This will remove the tag from all notes. Notes themselves will not be deleted."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response):
            if response == "delete":
                self.db.delete_tag(tag_name)
                if self.active_filter_type == "tag" and self.active_category_name == tag_name:
                    self.active_filter_type = "all"
                    self.active_category_name = ""
                    self.emit("filter-changed", "all", "")
                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

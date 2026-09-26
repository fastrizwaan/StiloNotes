# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject

from stilonotes.database import NoteDatabase
from stilonotes.notes_list import NotesList
from stilonotes.sidebar import Sidebar


class IndexView(Adw.BreakpointBin):
    __gtype_name__ = "IndexView"

    __gsignals__ = {
        "note-opened": (GObject.SignalFlags.RUN_FIRST, None, (object, bool)),
        "create-note": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db: NoteDatabase):
        super().__init__()
        self.set_size_request(360, 100)
        self.db = db

        self.active_filter_type = "all"
        self.active_category_name = ""
        self.active_tag_name = ""
        self.search_query = ""

        self._build_ui()
        self._setup_breakpoint()
        self.refresh()

    def _build_ui(self):
        self.split_view = Adw.OverlaySplitView()
        self.split_view.set_sidebar_width_fraction(0.3)
        self.split_view.set_max_sidebar_width(320)
        self.split_view.set_min_sidebar_width(240)
        self.split_view.set_collapsed(False)
        self.split_view.set_show_sidebar(True)
        self.split_view.set_pin_sidebar(True)

        # 1. Sidebar
        self.sidebar = Sidebar(self.db)
        self.sidebar.connect("filter-changed", self._on_sidebar_filter_changed)
        self.sidebar.connect("close-requested", lambda _sb: self.split_view.set_show_sidebar(False))
        self.split_view.set_sidebar(self.sidebar)

        # 2. Content Area
        self.toolbar_view = Adw.ToolbarView()
        self.toolbar_view.set_hexpand(True)

        # Header Stack (Main, Search, Selection)
        self.header_stack = Gtk.Stack()
        self.header_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Main Headerbar
        self.main_header = Adw.HeaderBar()
        self.main_header.set_show_back_button(False)

        # Sidebar toggle button (visible on mobile / collapsed)
        self.sidebar_toggle_btn = Gtk.Button()
        self.sidebar_toggle_btn.set_icon_name("sidebar-show-symbolic")
        self.sidebar_toggle_btn.set_tooltip_text("Open Categories (Ctrl+\\)")
        self.sidebar_toggle_btn.connect("clicked", lambda _b: self.toggle_sidebar())
        self.sidebar_toggle_btn.set_visible(False)
        self.main_header.pack_start(self.sidebar_toggle_btn)

        # New Note button (flat icon button, matching Iotas)
        self.new_note_btn = Gtk.Button()
        self.new_note_btn.set_icon_name("list-add-symbolic")
        self.new_note_btn.set_tooltip_text("New Note (Ctrl+N)")
        self.new_note_btn.connect("clicked", lambda _b: self.emit("create-note"))
        self.main_header.pack_start(self.new_note_btn)

        # Window Title Widget
        self.window_title = Adw.WindowTitle(title="All Notes")
        self.main_header.set_title_widget(self.window_title)

        # Menu button (visible on mobile / when sidebar menu is hidden)
        self.main_menu_btn = Gtk.MenuButton()
        self.main_menu_btn.set_icon_name("open-menu-symbolic")
        self.main_menu_btn.set_tooltip_text("Main Menu")
        self.main_menu_btn.set_menu_model(self._create_main_menu())
        self.main_menu_btn.set_visible(False)
        self.main_header.pack_end(self.main_menu_btn)

        # Search button
        self.search_btn = Gtk.Button()
        self.search_btn.set_icon_name("system-search-symbolic")
        self.search_btn.set_tooltip_text("Search Notes (Ctrl+F)")
        self.search_btn.connect("clicked", lambda _b: self.enter_search())
        self.main_header.pack_end(self.search_btn)

        # Selection mode button
        self.select_btn = Gtk.Button()
        self.select_btn.set_icon_name("selection-mode-symbolic")
        self.select_btn.set_tooltip_text("Select Notes")
        self.select_btn.connect("clicked", lambda _b: self.enter_selection_mode())
        self.main_header.pack_end(self.select_btn)

        self.header_stack.add_named(self.main_header, "main")

        # Search Headerbar
        self.search_header = Adw.HeaderBar()
        self.search_header.set_show_back_button(False)
        self.search_header.set_show_end_title_buttons(False)
        self.search_header.set_show_start_title_buttons(False)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search notes or #tags…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_text_changed)
        self.search_entry.connect("stop-search", lambda _e: self.exit_search())
        search_box.append(self.search_entry)

        close_search_btn = Gtk.Button(label="Done")
        close_search_btn.add_css_class("flat")
        close_search_btn.connect("clicked", lambda _b: self.exit_search())
        search_box.append(close_search_btn)

        self.search_header.set_title_widget(search_box)
        self.header_stack.add_named(self.search_header, "search")

        # Selection Headerbar
        self.selection_header = Adw.HeaderBar()
        self.selection_header.set_show_back_button(False)
        self.selection_header.set_show_end_title_buttons(False)
        self.selection_header.set_show_start_title_buttons(False)

        done_select_btn = Gtk.Button(label="Done")
        done_select_btn.add_css_class("suggested-action")
        done_select_btn.connect("clicked", lambda _b: self.exit_selection_mode())
        self.selection_header.pack_start(done_select_btn)

        select_all_btn = Gtk.Button(label="Select All")
        select_all_btn.add_css_class("flat")
        select_all_btn.connect("clicked", lambda _b: self.notes_list.select_all(True))
        self.selection_header.pack_start(select_all_btn)

        self.selection_title = Adw.WindowTitle(title="Select Notes")
        self.selection_header.set_title_widget(self.selection_title)

        delete_selected_btn = Gtk.Button()
        delete_selected_btn.set_icon_name("user-trash-symbolic")
        delete_selected_btn.add_css_class("destructive-action")
        delete_selected_btn.set_tooltip_text("Delete Selected")
        delete_selected_btn.connect("clicked", lambda _b: self._on_delete_selected())
        self.selection_header.pack_end(delete_selected_btn)

        self.header_stack.add_named(self.selection_header, "selection")

        self.toolbar_view.add_top_bar(self.header_stack)

        # Notes List inside Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.notes_list = NotesList(self.db)
        self.notes_list.connect("note-selected", lambda _nl, note: self.emit("note-opened", note, False))
        self.notes_list.connect("new-note-requested", lambda _nl: self.emit("create-note"))
        self.notes_list.connect("note-pin-toggled", lambda _nl, _id: self.refresh())
        self.notes_list.connect("note-deleted", lambda _nl, nid: self._on_note_deleted(nid))
        self.notes_list.connect("note-duplicated", lambda _nl, nid: self._on_note_duplicated(nid))

        self.toast_overlay.set_child(self.notes_list)
        self.toolbar_view.set_content(self.toast_overlay)
        self.split_view.set_content(self.toolbar_view)

        self.set_child(self.split_view)

    def _setup_breakpoint(self):
        cond = Adw.breakpoint_condition_parse("max-width: 700sp")
        bp = Adw.Breakpoint.new(cond)
        bp.connect("apply", self._on_breakpoint_apply)
        bp.connect("unapply", self._on_breakpoint_unapply)
        self.add_breakpoint(bp)

        # Initial button configuration (desktop mode by default)
        self._update_header_buttons(is_collapsed=False)

    def _on_breakpoint_apply(self, _bp):
        self.split_view.set_pin_sidebar(False)
        self.split_view.set_collapsed(True)
        self.split_view.set_show_sidebar(False)
        self._update_header_buttons(is_collapsed=True)

    def _on_breakpoint_unapply(self, _bp):
        self.split_view.set_pin_sidebar(True)
        self.split_view.set_collapsed(False)
        self.split_view.set_show_sidebar(True)
        self._update_header_buttons(is_collapsed=False)

    def _update_header_buttons(self, is_collapsed: bool):
        if is_collapsed:
            self.sidebar_toggle_btn.set_visible(True)
            self.sidebar.show_buttons(show_close=True, show_menu=False)
            self.main_menu_btn.set_visible(True)
        else:
            self.sidebar_toggle_btn.set_visible(False)
            self.sidebar.show_buttons(show_close=False, show_menu=True)
            self.main_menu_btn.set_visible(False)

    def _create_main_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append("About Stilo Notes", "app.about")
        return menu

    def refresh(self, update_sidebar: bool = True):
        """Fetch filtered notes and reload list."""
        if update_sidebar:
            self.sidebar.refresh()

        # Update title
        if self.active_tag_name:
            self.window_title.set_title(f"#{self.active_tag_name}")
        elif self.active_filter_type == "all":
            self.window_title.set_title("All Notes")
        elif self.active_filter_type == "uncategorized":
            self.window_title.set_title("Uncategorized")
        elif self.active_filter_type == "pinned":
            self.window_title.set_title("Favorites")
        elif self.active_filter_type == "todo":
            self.window_title.set_title("Tasks")
        elif self.active_filter_type == "trash":
            self.window_title.set_title("Trash")
        elif self.active_filter_type == "category":
            self.window_title.set_title(self.active_category_name or "Category")

        notes = self.db.get_notes(
            filter_type=self.active_filter_type,
            category_name=self.active_category_name,
            tag_name=self.active_tag_name,
            search_query=self.search_query
        )
        self.notes_list.set_notes(
            notes,
            is_search=bool(self.search_query),
            active_filter_type=self.active_filter_type,
            active_category_name=self.active_category_name
        )

    def _on_sidebar_filter_changed(self, _sb, filter_type: str, category_name: str):
        self.active_filter_type = filter_type
        self.active_category_name = category_name
        self.active_tag_name = ""

        if self.split_view.get_collapsed():
            self.split_view.set_show_sidebar(False)

        self.refresh(update_sidebar=False)

    def filter_by_tag(self, tag_name: str):
        self.active_tag_name = tag_name
        self.active_filter_type = "all"
        self.refresh()

    def enter_search(self):
        self.header_stack.set_visible_child_name("search")
        self.search_entry.grab_focus()

    def exit_search(self):
        self.search_query = ""
        self.search_entry.set_text("")
        self.header_stack.set_visible_child_name("main")
        self.refresh()

    def _on_search_text_changed(self, entry):
        self.search_query = entry.get_text().strip()
        self.refresh(update_sidebar=False)

    def enter_selection_mode(self):
        self.notes_list.set_selection_mode(True)
        self.header_stack.set_visible_child_name("selection")

    def exit_selection_mode(self):
        self.notes_list.set_selection_mode(False)
        self.header_stack.set_visible_child_name("main")

    def _on_delete_selected(self):
        checked = self.notes_list.get_checked_notes()
        if not checked:
            return
        for n in checked:
            self.db.delete_note(n.id)
        self.exit_selection_mode()
        self.refresh()

    def _on_note_deleted(self, note_id: str):
        self.db.delete_note(note_id)
        self.refresh()

    def _on_note_duplicated(self, note_id: str):
        dup = self.db.duplicate_note(note_id)
        self.refresh()
        if dup:
            self.emit("note-opened", dup, False)

    def toggle_sidebar(self):
        is_show = self.split_view.get_show_sidebar()
        self.split_view.set_show_sidebar(not is_show)

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject

from stilonotes.models import Note
from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.index import IndexView
from stilonotes.editor import NoteEditor
from stilonotes.const import APP_ID, IS_DEVEL

class StiloWindow(Adw.ApplicationWindow):
    __gtype_name__ = "StiloWindow"

    def __init__(self, app: Adw.Application, db: NoteDatabase):
        super().__init__(application=app)
        self.db = db
        self.config_manager = ConfigManager.get_default(db)

        self.set_title("Stilo Notes")
        self.set_icon_name(APP_ID)
        self.add_css_class("stilo-window")
        if IS_DEVEL:
            self.add_css_class("devel")

        self._build_ui()
        self._setup_actions()
        self._setup_theme()
        self._restore_session()
        self.db.add_change_listener(self._on_db_changed)

    def _build_ui(self):
        self.navigation = Adw.NavigationView()

        # 1. Index Page
        self.index_view = IndexView(self.db)
        self.index_view.connect("note-opened", self._on_note_opened)
        self.index_view.connect("create-note", self._on_create_note)

        self.index_page = Adw.NavigationPage.new(self.index_view, "Notes")
        self.index_page.connect("shown", lambda _p: self.index_view.refresh(update_sidebar=False))
        self.navigation.add(self.index_page)

        # 2. Editor Page
        self.editor = NoteEditor(self.db)
        self.editor.setup_actions(self)
        self.editor.connect("note-updated", self._on_note_updated)
        self.editor.connect("note-deleted", self._on_editor_note_deleted)
        self.editor.connect("note-pin-toggled", self._on_editor_note_pin_toggled)
        self.editor.connect("note-duplicated", self._on_editor_note_duplicated)
        self.editor.connect("note-category-changed", self._on_editor_category_changed)
        self.editor.connect("tag-clicked", self._on_editor_tag_clicked)
        self.editor.connect("open-note-link", self._on_editor_open_note_link)
        self.editor.connect("back", self._on_editor_back)
        self.editor.connect("toggle-app-theme", lambda _ed: self._toggle_theme())

        self.editor_page = Adw.NavigationPage.new(self.editor, "Editor")
        self.editor_page.set_can_pop(True)
        self.editor_page.connect("shown", lambda _p: self.editor.focus_editor())

        self.set_content(self.navigation)

        # Connect close-request to remember state
        self.connect("close-request", self._on_close_request)

    def _setup_actions(self):
        action_group = Gio.SimpleActionGroup()

        # Create note
        act_create = Gio.SimpleAction.new("create-note", None)
        act_create.connect("activate", lambda _a, _p: self._on_create_note(None))
        action_group.add_action(act_create)
        self.get_application().set_accels_for_action("win.create-note", ["<Control>n"])

        # Search
        act_search = Gio.SimpleAction.new("search", None)
        act_search.connect("activate", lambda _a, _p: self.index_view.enter_search())
        action_group.add_action(act_search)
        self.get_application().set_accels_for_action("win.search", ["<Control>f"])

        # Go back
        act_back = Gio.SimpleAction.new("go-back", None)
        act_back.connect("activate", lambda _a, _p: self._go_back())
        action_group.add_action(act_back)
        self.get_application().set_accels_for_action("win.go-back", ["Escape", "<Alt>Left"])

        # Toggle sidebar
        act_sidebar = Gio.SimpleAction.new("toggle-sidebar", None)
        act_sidebar.connect("activate", lambda _a, _p: self.index_view.toggle_sidebar())
        action_group.add_action(act_sidebar)
        self.get_application().set_accels_for_action("win.toggle-sidebar", ["<Control>backslash"])

        # Toggle Theme
        act_theme = Gio.SimpleAction.new("toggle-theme", None)
        act_theme.connect("activate", lambda _a, _p: self._toggle_theme())
        action_group.add_action(act_theme)
        self.get_application().set_accels_for_action("win.toggle-theme", ["<Control><Shift>d"])

        # Toggle View Mode (List / Grid)
        act_view_mode = Gio.SimpleAction.new("toggle-view-mode", None)
        act_view_mode.connect("activate", lambda _a, _p: self.index_view.toggle_view_mode())
        action_group.add_action(act_view_mode)
        self.get_application().set_accels_for_action("win.toggle-view-mode", ["<Control>g"])

        self.insert_action_group("win", action_group)

    def _setup_theme(self):
        style_manager = Adw.StyleManager.get_default()
        mode = self.config_manager.get_theme_mode()

        if mode == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif mode == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        is_dark = style_manager.get_dark()
        self.editor.update_theme(is_dark)

        style_manager.connect("notify::dark", lambda sm, _p: self.editor.update_theme(sm.get_dark()))

    def _toggle_theme(self):
        style_manager = Adw.StyleManager.get_default()
        is_dark = not style_manager.get_dark()
        scheme = Adw.ColorScheme.FORCE_DARK if is_dark else Adw.ColorScheme.FORCE_LIGHT
        style_manager.set_color_scheme(scheme)
        self.config_manager.set_theme_mode("dark" if is_dark else "light")
        self.editor.update_theme(is_dark)
        if hasattr(self.editor, "theme_selector"):
            self.editor.theme_selector.populate()

    def _restore_session(self):
        w, h = self.config_manager.get_window_size()
        self.set_default_size(w, h)
        if self.config_manager.get_window_maximized():
            self.maximize()
        # Always start on All Notes view (do not auto-open or create notes on launch)
        self.config_manager.set_last_opened_note_id("")

    def _on_close_request(self, _win):
        # Unsubscribe db change listener
        if hasattr(self, "db") and self.db:
            self.db.remove_change_listener(self._on_db_changed)
        # Flush any pending editor changes
        if hasattr(self, "editor"):
            self.editor.flush_save()
        # Save window geometry
        w = self.get_width()
        h = self.get_height()
        self.config_manager.set_window_size(w, h)
        self.config_manager.set_window_maximized(self.is_maximized())
        return False

    def open_note(self, note: Note, immediate: bool = False):
        """Open a note in the editor and navigate to it."""
        full_note = self.db.get_note(note.id)
        self.editor.load_note(full_note or note)
        self.config_manager.set_last_opened_note_id(note.id)

        visible_page = self.navigation.get_visible_page()
        if visible_page != self.editor_page:
            if immediate:
                self.navigation.push_by_tag("editor") if False else self.navigation.push(self.editor_page)
            else:
                self.navigation.push(self.editor_page)
        GLib.idle_add(self.editor.focus_editor)
        GLib.timeout_add(100, self.editor.focus_editor)
        GLib.timeout_add(250, self.editor.focus_editor)

    def _on_note_opened(self, _iv, note: Note, immediate: bool):
        self.open_note(note, immediate)

    def _on_create_note(self, _iv):
        category = self.index_view.active_category_name if self.index_view.active_filter_type == "category" else ""
        note = self.db.create_note(title="Untitled Note", category=category, sender=self)
        self.index_view.refresh()
        full_note = self.db.get_note(note.id)
        self.open_note(full_note or note, immediate=False)

    def _on_note_updated(self, _ed, note_id: str, title: str, excerpt: str, html: str, md: str, tags: list, has_todo: bool):
        if self.navigation.get_visible_page() != self.editor_page:
            self.index_view.refresh(update_sidebar=False)

    def _on_editor_note_deleted(self, _ed, note_id: str):
        self.db.delete_note(note_id, sender=self)
        self._go_back()
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_note_pin_toggled(self, _ed, note_id: str):
        self.db.toggle_pin_note(note_id, sender=self)
        # Reflect current note pin state in the star button
        if self.editor.current_note and self.editor.current_note.id == note_id:
            self.editor._update_star_btn(self.editor.current_note.is_pinned)
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_note_duplicated(self, _ed, note_id: str):
        dup = self.db.duplicate_note(note_id)
        self.index_view.refresh(update_sidebar=True)
        if dup:
            self.open_note(dup, immediate=False)

    def _on_db_changed(self, event_type: str, data: dict, sender: Any):
        # Ignore events originating from this window or its child components
        if sender in (self, getattr(self, "editor", None), getattr(self, "index_view", None)):
            return

        is_in_editor = (self.navigation.get_visible_page() == self.editor_page)
        curr_note = self.editor.current_note if hasattr(self, "editor") else None
        curr_note_id = curr_note.id if curr_note else None

        if event_type == "note-saved":
            note_id = data.get("note_id")
            if is_in_editor and curr_note_id == note_id:
                # Same note is open in this window!
                if self.editor.has_pending_changes():
                    # Local window has pending unsaved changes -> show conflict banner
                    self.editor.show_conflict_banner()
                else:
                    # Clean reload from DB
                    full = self.db.get_note(note_id)
                    if full:
                        self.editor.reload_note_from_db(full)
            else:
                self.index_view.refresh(update_sidebar=True)
                if is_in_editor:
                    self.editor._sync_autocomplete_data()

        elif event_type in ("note-deleted", "notes-deleted"):
            deleted_ids = [data.get("note_id")] if event_type == "note-deleted" else data.get("note_ids", [])
            if is_in_editor and curr_note_id in deleted_ids:
                is_perm = data.get("permanent", False)
                self._go_back()
                msg = "Note permanently deleted in another window" if is_perm else "Note moved to trash in another window"
                self.index_view.toast_overlay.add_toast(Adw.Toast.new(msg))
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "trash-emptied":
            if is_in_editor and curr_note and curr_note.is_trashed:
                self._go_back()
                self.index_view.toast_overlay.add_toast(Adw.Toast.new("Trash was emptied in another window"))
            self.index_view.refresh(update_sidebar=True)

        elif event_type in ("note-restored", "notes-restored"):
            restored_ids = [data.get("note_id")] if event_type == "note-restored" else data.get("note_ids", [])
            if is_in_editor and curr_note_id in restored_ids:
                if self.editor.current_note:
                    self.editor.current_note.is_trashed = False
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "note-pin-toggled":
            pinned_id = data.get("note_id")
            if is_in_editor and curr_note_id == pinned_id:
                is_pinned = data.get("is_pinned")
                if is_pinned is not None:
                    self.editor.current_note.is_pinned = is_pinned
                    self.editor._update_star_btn(is_pinned)
            self.index_view.refresh(update_sidebar=True)

        elif event_type in ("category-changed", "categories-updated"):
            if is_in_editor and curr_note_id:
                full = self.db.get_note(curr_note_id)
                if full:
                    self.editor.current_note.category = full.category
                    self.editor.category_header_bar.set_category(full.category)
                self.editor._sync_autocomplete_data()
            self.index_view.refresh(update_sidebar=True)

    def _on_editor_category_changed(self, _ed, note_id: str, new_category: str):
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_tag_clicked(self, _ed, tag_name: str):
        self._go_back()
        self.index_view.filter_by_tag(tag_name)

    def _on_editor_open_note_link(self, _ed, note_title: str):
        target = self.db.find_note_by_title(note_title)
        if not target:
            target = self.db.create_note(title=note_title, initial_text=f"# {note_title}\n\n")
            self.index_view.refresh()
        self.open_note(target)

    def _on_editor_back(self, _ed):
        self._go_back()

    def _go_back(self):
        if self.navigation.get_visible_page() == self.editor_page:
            if hasattr(self.editor, "header_stack") and self.editor.header_stack.get_visible_child_name() == "category":
                self.editor.header_stack.set_visible_child_name("main")
                return
            self.editor.flush_save()
            self.navigation.pop()
            self.index_view.refresh(update_sidebar=True)
            self.config_manager.set_last_opened_note_id("")

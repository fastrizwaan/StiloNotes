# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject, Gdk

from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.theme_selector import ThemeSelector
from stilonotes.notes_list import NotesList
from stilonotes.sidebar import Sidebar
from stilonotes.selection_header_bar import SelectionHeaderBar
from stilonotes.exporter import export_note_dialog, export_notes_dialog


class IndexView(Adw.Bin):
    __gtype_name__ = "IndexView"

    __gsignals__ = {
        "note-opened": (GObject.SignalFlags.RUN_FIRST, None, (object, bool)),
        "create-note": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db: NoteDatabase, sidebar: Optional[Sidebar] = None):
        super().__init__()
        self.set_size_request(360, 100)
        self.db = db
        self.config_manager = ConfigManager.get_default(self.db)

        self.active_filter_type = "all"
        self.active_category_name = ""
        self.search_query = ""
        self._search_debounce_id = None
        self._private_unlocked = False

        self.sidebar = sidebar or Sidebar(self.db)
        self.sidebar.connect("filter-changed", self._on_sidebar_filter_changed)

        self.notes_list = NotesList(self.db, view_mode=self.config_manager.get_view_mode())
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Content Area
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
        self.theme_selector = ThemeSelector(self.config_manager)
        self.main_menu_btn.get_popover().add_child(self.theme_selector, "theme")
        self.main_menu_btn.set_visible(False)
        self.main_header.pack_end(self.main_menu_btn)

        # Search button
        self.search_btn = Gtk.Button()
        self.search_btn.set_icon_name("system-search-symbolic")
        self.search_btn.set_tooltip_text("Search Notes (Ctrl+F)")
        self.search_btn.connect("clicked", lambda _b: self.enter_search())
        self.main_header.pack_end(self.search_btn)

        # View toggle button (grid / list)
        self.view_toggle_btn = Gtk.Button()
        self._update_view_toggle_button()
        self.view_toggle_btn.connect("clicked", lambda _b: self.toggle_view_mode())
        self.main_header.pack_end(self.view_toggle_btn)

        # Selection mode button
        self.select_btn = Gtk.Button()
        self.select_btn.set_icon_name("selection-mode-symbolic")
        self.select_btn.set_tooltip_text("Select Notes")
        self.select_btn.connect("clicked", lambda _b: self.enter_selection_mode())
        self.main_header.pack_end(self.select_btn)

        # Private Notes Unlock / Lock button
        self.private_unlock_btn = Gtk.Button()
        self.private_unlock_btn.set_icon_name("channel-secure-symbolic")
        self.private_unlock_btn.set_label("Unlock")
        self.private_unlock_btn.set_tooltip_text("Unlock Private Notes")
        self.private_unlock_btn.set_visible(False)
        self.private_unlock_btn.connect("clicked", self._on_private_unlock_clicked)
        self.main_header.pack_end(self.private_unlock_btn)

        self.header_stack.add_named(self.main_header, "main")

        # Search Headerbar
        self.search_header = Adw.HeaderBar()
        self.search_header.set_show_back_button(False)
        self.search_header.set_show_end_title_buttons(False)
        self.search_header.set_show_start_title_buttons(False)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search notes…")
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
        self.selection_header = SelectionHeaderBar()
        self.selection_header.connect("abort", lambda _shb: self.exit_selection_mode())
        self.selection_header.connect("select-all", lambda _shb: self.notes_list.select_all(True))
        self.selection_header.connect("categories-changed", self._on_selection_categories_changed)
        self.selection_header.connect("set-favourite", self._on_selection_toggle_favourite)
        self.selection_header.connect("export", self._on_selection_export)
        self.selection_header.connect("delete", self._on_selection_delete)
        self.header_stack.add_named(self.selection_header, "selection")

        self.toolbar_view.add_top_bar(self.header_stack)

        # Empty Trash Bar
        self.empty_trash_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.empty_trash_bar.add_css_class("empty-trash-bar")
        self.empty_trash_bar.set_visible(False)

        empty_trash_spacer = Gtk.Box(hexpand=True)
        self.empty_trash_bar.append(empty_trash_spacer)

        self.empty_trash_btn = Gtk.Button(label="Empty Trash…")
        self.empty_trash_btn.add_css_class("empty-trash-button")
        self.empty_trash_btn.connect("clicked", self._on_empty_trash_clicked)
        self.empty_trash_bar.append(self.empty_trash_btn)

        self.toolbar_view.add_top_bar(self.empty_trash_bar)


        # Notes List inside Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()
        self.notes_list.connect("note-selected", lambda _nl, note: self.emit("note-opened", note, False))
        self.notes_list.connect("locked-note-clicked", lambda _nl, note: self._prompt_unlock_private(target_note=note))
        self.notes_list.connect("new-note-requested", lambda _nl: self.emit("create-note"))
        self.notes_list.connect("note-pin-toggled", lambda _nl, _id: self.refresh())
        self.notes_list.connect("note-copy-link", lambda _nl, nid: self._on_note_copy_link(nid))
        self.notes_list.connect("note-deleted", lambda _nl, nid: self._on_note_deleted(nid))
        self.notes_list.connect("note-duplicated", lambda _nl, nid: self._on_note_duplicated(nid))
        self.notes_list.connect("selection-changed", self._on_selection_changed)

        self.toast_overlay.set_child(self.notes_list)
        self.toolbar_view.set_content(self.toast_overlay)

        self.set_child(self.toolbar_view)

    def update_header_buttons(self, is_collapsed: bool):
        if is_collapsed:
            self.sidebar_toggle_btn.set_visible(True)
            self.sidebar.show_buttons(show_close=True, show_menu=False)
            self.main_menu_btn.set_visible(True)
        else:
            self.sidebar_toggle_btn.set_visible(False)
            self.sidebar.show_buttons(show_close=False, show_menu=True)
            self.main_menu_btn.set_visible(False)

    def _update_header_buttons(self, is_collapsed: bool):
        self.update_header_buttons(is_collapsed)

    def _create_main_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        s_theme = Gio.Menu()
        item_theme = Gio.MenuItem.new(None, None)
        item_theme.set_attribute_value("custom", GLib.Variant.new_string("theme"))
        s_theme.append_item(item_theme)
        menu.append_section(None, s_theme)

        s_window = Gio.Menu()
        s_window.append("Open…", "win.open-file")
        s_window.append("New Window", "app.new-window")
        menu.append_section(None, s_window)

        s_app = Gio.Menu()
        s_app.append("Preferences", "app.preferences")
        s_app.append("Keyboard Shortcuts", "app.shortcuts")
        s_app.append("About Stilo Notes", "app.about")
        menu.append_section(None, s_app)
        return menu

    def _on_empty_trash_clicked(self, _btn):
        dialog = Adw.AlertDialog.new(
            "Empty Trash?",
            "All notes in the trash will be permanently deleted."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("empty", "Empty Trash")
        dialog.set_response_appearance("empty", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_d, response):
            if response == "empty":
                self.db.empty_trash(sender=self)
                self.refresh(update_sidebar=True)
                self.toast_overlay.add_toast(Adw.Toast.new("Trash emptied"))

        dialog.connect("response", on_response)
        root = self.get_root()
        if root:
            dialog.present(root)
        else:
            dialog.present(self)

    def refresh(self, update_sidebar: bool = True):
        """Fetch filtered notes and reload list."""
        if update_sidebar:
            self.sidebar.refresh()

        is_trash = (self.active_filter_type == "trash")
        self.new_note_btn.set_visible(not is_trash)

        # Update title
        if self.active_filter_type == "all":
            self.window_title.set_title("All Notes")
        elif self.active_filter_type == "uncategorized":
            self.window_title.set_title("Uncategorized")
        elif self.active_filter_type in ("pinned", "favorites"):
            self.window_title.set_title("Favorites")
        elif self.active_filter_type in ("private", "locked"):
            self.window_title.set_title("Private Notes")
        elif self.active_filter_type in ("todo", "todos"):
            self.window_title.set_title("Todos")
        elif self.active_filter_type in ("list", "lists"):
            self.window_title.set_title("Lists")
        elif self.active_filter_type in ("linked", "link", "links"):
            self.window_title.set_title("Linked Notes")
        elif self.active_filter_type in ("recent", "recents"):
            self.window_title.set_title("Recent")
        elif is_trash:
            self.window_title.set_title("Trash")
        elif self.active_filter_type == "category":
            self.window_title.set_title(self.active_category_name or "Category")
        elif self.active_filter_type == "tag":
            self.window_title.set_title(f"#{self.active_category_name}")

        is_private = (self.active_filter_type in ("private", "locked"))
        is_private_locked = is_private and not self._private_unlocked
        self.search_btn.set_visible(not is_private_locked)
        self.select_btn.set_visible(not is_private_locked)
        if is_private:
            self.private_unlock_btn.set_visible(True)
            if not self.db.has_private_password():
                self.private_unlock_btn.set_label("Set Password")
                self.private_unlock_btn.set_tooltip_text("Set Private Note Password")
                self.private_unlock_btn.add_css_class("suggested-action")
            elif self._private_unlocked:
                self.private_unlock_btn.set_label("Lock")
                self.private_unlock_btn.set_tooltip_text("Lock Private Notes")
                self.private_unlock_btn.remove_css_class("suggested-action")
            else:
                self.private_unlock_btn.set_label("Unlock")
                self.private_unlock_btn.set_tooltip_text("Unlock Private Notes")
                self.private_unlock_btn.add_css_class("suggested-action")
        else:
            self.private_unlock_btn.set_visible(False)

        notes = self.db.get_notes(
            filter_type=self.active_filter_type,
            category_name=self.active_category_name,
            tag_name=self.active_category_name if self.active_filter_type == "tag" else "",
            search_query=self.search_query
        )

        self.empty_trash_bar.set_visible(is_trash and len(notes) > 0)

        self.notes_list.set_notes(
            notes,
            is_search=bool(self.search_query),
            active_filter_type=self.active_filter_type,
            active_category_name=self.active_category_name,
            is_private_unlocked=self._private_unlocked
        )

    def filter_by_tag(self, tag_name: str):
        """Programmatically switch filter to a specific tag."""
        clean_tag = tag_name.strip().lstrip("#")
        self.active_filter_type = "tag"
        self.active_category_name = clean_tag
        self.sidebar.active_filter_type = "tag"
        self.sidebar.active_category_name = clean_tag
        self.refresh()

    def _on_sidebar_filter_changed(self, _sb, filter_type: str, category_name: str):
        if filter_type not in ("private", "locked"):
            self._private_unlocked = False
        else:
            if getattr(self, "notes_list", None) and self.notes_list.selection_mode:
                self.exit_selection_mode()
            if getattr(self, "header_stack", None) and self.header_stack.get_visible_child_name() == "search":
                self.exit_search()

        self.active_filter_type = filter_type
        self.active_category_name = category_name

        self.refresh(update_sidebar=False)

    def enter_search(self):
        if self.active_filter_type in ("private", "locked") and not self._private_unlocked:
            return
        self.header_stack.set_visible_child_name("search")
        self.search_entry.grab_focus()

    def exit_search(self):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None
        self.search_query = ""
        self.search_entry.set_text("")
        self.header_stack.set_visible_child_name("main")
        self.refresh()

    def destroy_view(self):
        """Cancel any pending search debouncing timeout to avoid leaks."""
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None

    def _on_search_text_changed(self, entry):
        if self._search_debounce_id:
            GLib.source_remove(self._search_debounce_id)
            self._search_debounce_id = None

        def do_search():
            self._search_debounce_id = None
            query = entry.get_text().strip()
            if query != self.search_query:
                self.search_query = query
                self.refresh(update_sidebar=False)
            return False

        self._search_debounce_id = GLib.timeout_add(150, do_search)

    def _on_selection_changed(self, _nl, count: int):
        checked = self.notes_list.get_checked_notes()
        self.selection_header.set_selected_notes(checked)

    def enter_selection_mode(self):
        if self.active_filter_type in ("private", "locked") and not self._private_unlocked:
            return
        self.notes_list.set_selection_mode(True)
        cats = [c.name for c in self.db.get_categories()]
        self.selection_header.set_categories_model(cats)
        self.selection_header.activate()
        self.header_stack.set_visible_child_name("selection")

    def exit_selection_mode(self):
        self.selection_header.deactivate()
        self.notes_list.set_selection_mode(False)
        self.header_stack.set_visible_child_name("main")

    def _on_selection_categories_changed(self, _shb, new_category: str):
        checked = self.notes_list.get_checked_notes()
        if not checked:
            return
        clean_cat = (new_category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""
        ids = [n.id for n in checked]
        self.db.set_notes_category(ids, clean_cat)
        self.exit_selection_mode()
        self.refresh()
        msg = f"Changed category to '{clean_cat}' for {len(ids)} notes" if clean_cat else f"Removed category from {len(ids)} notes"
        self.toast_overlay.add_toast(Adw.Toast.new(msg))

    def _on_selection_toggle_favourite(self, _shb):
        checked = self.notes_list.get_checked_notes()
        if not checked:
            return
        set_count = len([n for n in checked if n.is_pinned])
        unset_count = len(checked) - set_count
        new_state = False if set_count >= unset_count else True
        ids = [n.id for n in checked]
        self.db.set_notes_pinned(ids, new_state)
        self.exit_selection_mode()
        self.refresh()
        msg = f"Added {len(ids)} notes to Favorites" if new_state else f"Removed {len(ids)} notes from Favorites"
        self.toast_overlay.add_toast(Adw.Toast.new(msg))

    def _on_selection_export(self, _shb):
        checked = self.notes_list.get_checked_notes()
        if not checked:
            return
        root = self.get_root()
        if len(checked) == 1:
            export_note_dialog(root, checked[0], on_complete=lambda msg: self.toast_overlay.add_toast(Adw.Toast.new(msg)), db=self.db)
        else:
            export_notes_dialog(root, checked, on_complete=lambda msg: self.toast_overlay.add_toast(Adw.Toast.new(msg)), db=self.db)

    def _on_selection_delete(self, _shb):
        checked = self.notes_list.get_checked_notes()
        if not checked:
            return
        ids = [n.id for n in checked]
        if self.active_filter_type == "trash":
            self.db.delete_notes(ids, permanent=True)
            self.exit_selection_mode()
            self.refresh()
            self.toast_overlay.add_toast(Adw.Toast.new(f"Permanently deleted {len(ids)} notes"))
        else:
            self.db.delete_notes(ids, permanent=False)
            self.exit_selection_mode()
            self.refresh()
            toast = Adw.Toast.new(f"Moved {len(ids)} notes to Trash")
            toast.set_button_label("Undo")
            toast.connect("button-clicked", lambda _t: (self.db.restore_notes(ids), self.refresh()))
            self.toast_overlay.add_toast(toast)

    def _on_note_deleted(self, note_id: str):
        self.db.delete_note(note_id)
        self.refresh()

    
    def _on_note_copy_link(self, note_id: str):
        note = self.db.get_note(note_id)
        if note:
            display = Gdk.Display.get_default()
            if display:
                clip = display.get_clipboard()
                clip.set(f"[[{note.title}]]")
                self.toast_overlay.add_toast(Adw.Toast.new(f"Link to '{note.title}' copied"))

    def _on_note_duplicated(self, note_id: str):
        dup = self.db.duplicate_note(note_id)
        self.refresh()
        if dup:
            self.emit("note-opened", dup, False)

    def toggle_sidebar(self):
        root = self.get_root()
        if root and hasattr(root, "toggle_sidebar"):
            root.toggle_sidebar()

    def _update_view_toggle_button(self):
        is_grid = (self.notes_list.view_mode == "grid")
        self.view_toggle_btn.set_icon_name("view-list-symbolic" if is_grid else "view-grid-symbolic")
        self.view_toggle_btn.set_tooltip_text("Switch to List View (Ctrl+G)" if is_grid else "Switch to Grid View (Ctrl+G)")

    def toggle_view_mode(self):
        current = self.notes_list.view_mode
        new_mode = "grid" if current == "list" else "list"
        self.config_manager.set_view_mode(new_mode)
        self.notes_list.set_view_mode(new_mode)
        self._update_view_toggle_button()

    def _on_private_unlock_clicked(self, _btn):
        if not self.db.has_private_password():
            self._prompt_unlock_private()
        elif self._private_unlocked:
            if getattr(self, "notes_list", None) and self.notes_list.selection_mode:
                self.exit_selection_mode()
            if getattr(self, "header_stack", None) and self.header_stack.get_visible_child_name() == "search":
                self.exit_search()
            self._private_unlocked = False
            self.refresh()
            self.toast_overlay.add_toast(Adw.Toast.new("Private notes locked"))
        else:
            self._prompt_unlock_private()

    def _prompt_unlock_private(self, target_note=None, on_unlocked=None):
        window = self.get_root()
        if not self.db.has_private_password():
            dlg = Adw.AlertDialog.new(
                "Set Private Note Password",
                "Please set a master password to protect your private notes."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("save", "Set Password & Unlock")
            dlg.set_default_response("save")
            dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            grp = Adw.PreferencesGroup()
            pwd_row = Adw.PasswordEntryRow()
            pwd_row.set_title("New Password")
            grp.add(pwd_row)
            conf_row = Adw.PasswordEntryRow()
            conf_row.set_title("Confirm Password")
            grp.add(conf_row)
            box.append(grp)
            dlg.set_extra_child(box)

            def on_set_pwd_res(_d, resp):
                if resp != "save":
                    return
                p1 = pwd_row.get_text()
                p2 = conf_row.get_text()
                if not p1.strip():
                    err = Adw.AlertDialog.new("Password Required", "Password cannot be empty.")
                    err.add_response("ok", "OK")
                    err.present(window or self)
                    return
                if p1 != p2:
                    err = Adw.AlertDialog.new("Passwords Do Not Match", "The entered passwords do not match.")
                    err.add_response("ok", "OK")
                    err.present(window or self)
                    return
                self.db.set_private_password(p1)
                self._private_unlocked = True
                self.refresh()
                self.toast_overlay.add_toast(Adw.Toast.new("Private notes unlocked"))
                if on_unlocked:
                    on_unlocked()
                elif target_note:
                    self.emit("note-opened", target_note, False)

            dlg.connect("response", on_set_pwd_res)
            dlg.present(window or self)
        else:
            dlg = Adw.AlertDialog.new(
                "Unlock Private Notes",
                "Enter Private Note Password to view locked notes."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("unlock", "Unlock")
            dlg.set_default_response("unlock")
            dlg.set_response_appearance("unlock", Adw.ResponseAppearance.SUGGESTED)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            grp = Adw.PreferencesGroup()
            pwd_row = Adw.PasswordEntryRow()
            pwd_row.set_title("Password")
            grp.add(pwd_row)
            box.append(grp)
            dlg.set_extra_child(box)

            def on_unlock_res(_d, resp):
                if resp != "unlock":
                    return
                p = pwd_row.get_text()
                if not self.db.verify_private_password(p):
                    err = Adw.AlertDialog.new("Incorrect Password", "The password you entered is incorrect.")
                    err.add_response("ok", "OK")
                    err.present(window or self)
                    return
                self._private_unlocked = True
                self.refresh()
                self.toast_overlay.add_toast(Adw.Toast.new("Private notes unlocked"))
                if on_unlocked:
                    on_unlocked()
                elif target_note:
                    self.emit("note-opened", target_note, False)

            dlg.connect("response", on_unlock_res)
            dlg.present(window or self)

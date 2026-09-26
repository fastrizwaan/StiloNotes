# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Optional, Set
from gi.repository import Adw, Gtk, GObject, Pango

from stilonotes.models import Note
from stilonotes.markdown_utils import format_relative_date

class NoteRow(Gtk.ListBoxRow):
    __gtype_name__ = "NoteRow"

    def __init__(self, note: Note, selection_mode: bool = False):
        super().__init__()
        self.note = note
        self.selection_mode = selection_mode
        self.add_css_class("stilo-note-row")

        self._build_ui()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # Checkbox for selection mode
        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_visible(self.selection_mode)
        self.checkbox.set_valign(Gtk.Align.CENTER)
        main_box.append(self.checkbox)

        # Text column
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        vbox.set_hexpand(True)

        # Title Row
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        if self.note.is_pinned:
            pin_img = Gtk.Image.new_from_icon_name("starred-symbolic")
            pin_img.add_css_class("stilo-pin-icon")
            title_box.append(pin_img)

        title_lbl = Gtk.Label(label=self.note.title or "Untitled Note")
        title_lbl.add_css_class("stilo-note-title")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_max_width_chars(32)
        title_box.append(title_lbl)

        vbox.append(title_box)

        # Excerpt
        excerpt_text = self.note.excerpt or "No additional text"
        excerpt_lbl = Gtk.Label(label=excerpt_text)
        excerpt_lbl.add_css_class("stilo-note-excerpt")
        excerpt_lbl.set_halign(Gtk.Align.START)
        excerpt_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        excerpt_lbl.set_lines(2)
        excerpt_lbl.set_wrap(True)
        vbox.append(excerpt_lbl)

        # Meta Row (Category / Tag pill + Date + Todo badge)
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        if self.note.category:
            cat_pill = Gtk.Label(label=self.note.category)
            cat_pill.add_css_class("stilo-tag-pill")
            meta_box.append(cat_pill)
        elif self.note.tags:
            tag_pill = Gtk.Label(label=f"#{self.note.tags[0]}")
            tag_pill.add_css_class("stilo-tag-pill")
            meta_box.append(tag_pill)

        if self.note.has_todo:
            todo_badge = Gtk.Label(label="☑ Todo")
            todo_badge.add_css_class("stilo-todo-badge")
            meta_box.append(todo_badge)

        date_lbl = Gtk.Label(label=format_relative_date(self.note.updated_at))
        date_lbl.add_css_class("stilo-note-meta")
        date_lbl.set_halign(Gtk.Align.START)
        meta_box.append(date_lbl)

        vbox.append(meta_box)
        main_box.append(vbox)

        self.set_child(main_box)

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        self.checkbox.set_visible(enabled)

    def is_checked(self) -> bool:
        return self.checkbox.get_active()

    def set_checked(self, checked: bool):
        self.checkbox.set_active(checked)


class NotesList(Gtk.Box):
    __gtype_name__ = "NotesList"

    __gsignals__ = {
        "note-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "note-pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-duplicated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-note-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.selection_mode = False
        self.current_notes: List[Note] = []

        self._build_ui()

    def _build_ui(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Scrolled List
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(680)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_margin_start(12)
        self.listbox.set_margin_end(12)
        self.listbox.set_margin_top(12)
        self.listbox.set_margin_bottom(24)
        self.listbox.connect("row-activated", self._on_row_activated)

        clamp.set_child(self.listbox)
        self.scrolled.set_child(clamp)
        self.stack.add_named(self.scrolled, "list")

        # 2. Empty Status Page
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_title("No Notes Found")
        self.empty_page.set_description("Capture your ideas, checklists, and notes in markdown.")
        self.empty_page.set_icon_name("document-edit-symbolic")

        new_btn = Gtk.Button(label="Create First Note")
        new_btn.add_css_class("pill")
        new_btn.add_css_class("suggested-action")
        new_btn.set_halign(Gtk.Align.CENTER)
        new_btn.connect("clicked", lambda _b: self.emit("new-note-requested"))
        self.empty_page.set_child(new_btn)
        self.stack.add_named(self.empty_page, "empty")

        # 3. Search Empty Page
        self.search_empty_page = Adw.StatusPage()
        self.search_empty_page.set_title("No Results Found")
        self.search_empty_page.set_description("Try searching with different keywords or tags.")
        self.search_empty_page.set_icon_name("system-search-symbolic")
        self.stack.add_named(self.search_empty_page, "search_empty")

        self.append(self.stack)

    def set_notes(self, notes: List[Note], is_search: bool = False):
        self.current_notes = notes

        # Clear existing rows
        while True:
            row = self.listbox.get_row_at_index(0)
            if not row:
                break
            self.listbox.remove(row)

        if not notes:
            if is_search:
                self.stack.set_visible_child_name("search_empty")
            else:
                self.stack.set_visible_child_name("empty")
            return

        self.stack.set_visible_child_name("list")
        for note in notes:
            row = NoteRow(note, self.selection_mode)
            self._setup_row_context_menu(row, note)
            self.listbox.append(row)

    def _setup_row_context_menu(self, row: NoteRow, note: Note):
        gesture = Gtk.GestureClick()
        gesture.set_button(3) # Right click

        def on_right_click(_g, _n, x, y):
            menu = Gio.Menu()
            pin_title = "Unpin Note" if note.is_pinned else "Pin to Top"
            menu.append(pin_title, f"row.pin::{note.id}")
            menu.append("Duplicate", f"row.duplicate::{note.id}")
            if note.is_trashed:
                menu.append("Restore Note", f"row.restore::{note.id}")
                menu.append("Delete Permanently", f"row.perm_delete::{note.id}")
            else:
                menu.append("Move to Trash", f"row.trash::{note.id}")

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(row)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup()

            act_pin = Gio.SimpleAction.new("pin", GLib.VariantType("s"))
            act_pin.connect("activate", lambda _a, p: self.emit("note-pin-toggled", p.get_string()))
            action_group.add_action(act_pin)

            act_dup = Gio.SimpleAction.new("duplicate", GLib.VariantType("s"))
            act_dup.connect("activate", lambda _a, p: self.emit("note-duplicated", p.get_string()))
            action_group.add_action(act_dup)

            act_trash = Gio.SimpleAction.new("trash", GLib.VariantType("s"))
            act_trash.connect("activate", lambda _a, p: self.emit("note-deleted", p.get_string()))
            action_group.add_action(act_trash)

            act_res = Gio.SimpleAction.new("restore", GLib.VariantType("s"))
            act_res.connect("activate", lambda _a, p: self._on_restore(p.get_string()))
            action_group.add_action(act_res)

            act_perm = Gio.SimpleAction.new("perm_delete", GLib.VariantType("s"))
            act_perm.connect("activate", lambda _a, p: self._on_perm_delete(p.get_string()))
            action_group.add_action(act_perm)

            row.insert_action_group("row", action_group)
            popover.popup()

        gesture.connect("pressed", on_right_click)
        row.add_controller(gesture)

    def _on_restore(self, note_id: str):
        self.db.restore_note(note_id)
        self.emit("note-pin-toggled", note_id) # triggers reload

    def _on_perm_delete(self, note_id: str):
        self.db.delete_note(note_id, permanent=True)
        self.emit("note-pin-toggled", note_id) # triggers reload

    def _on_row_activated(self, _lb, row: NoteRow):
        if not row:
            return
        if self.selection_mode:
            row.set_checked(not row.is_checked())
        else:
            self.emit("note-selected", row.note)

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        for i in range(len(self.current_notes)):
            row = self.listbox.get_row_at_index(i)
            if row and isinstance(row, NoteRow):
                row.set_selection_mode(enabled)

    def get_checked_notes(self) -> List[Note]:
        checked = []
        for i in range(len(self.current_notes)):
            row = self.listbox.get_row_at_index(i)
            if row and isinstance(row, NoteRow) and row.is_checked():
                checked.append(row.note)
        return checked

    def select_all(self, checked: bool = True):
        for i in range(len(self.current_notes)):
            row = self.listbox.get_row_at_index(i)
            if row and isinstance(row, NoteRow):
                row.set_checked(checked)

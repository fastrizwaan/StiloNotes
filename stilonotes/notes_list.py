# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime, timedelta
from typing import List, Optional
from gi.repository import Adw, Gtk, Gio, GLib, GObject, Pango

from stilonotes.models import Note
from stilonotes.markdown_utils import strip_markdown


class IndexRow(Gtk.ListBoxRow):
    __gtype_name__ = "IndexRow"

    __gsignals__ = {
        "pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplicate": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "restore": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "perm-delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, note: Note, selection_mode: bool = False, show_category_pill: bool = True):
        super().__init__()
        self.note = note
        self.show_category_pill = show_category_pill

        self._build_ui(selection_mode)
        self._setup_context_menu()

    def _build_ui(self, selection_mode: bool):
        # Outer box with Iotas-matched padding
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(14)
        box.set_margin_bottom(14)

        # Checkbox revealer for selection mode
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_reveal_child(selection_mode)

        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.set_margin_end(12)
        self.checkbox.connect("toggled", lambda _cb: self.emit("toggled", self.checkbox.get_active()))
        self.revealer.set_child(self.checkbox)
        box.append(self.revealer)

        # Note text column
        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_vbox.set_hexpand(True)

        # Title Label
        raw_title = self.note.title or "Untitled Note"
        clean_title = strip_markdown(raw_title) or "Untitled Note"
        self.title_lbl = Gtk.Label(label=clean_title)
        self.title_lbl.add_css_class("title")
        self.title_lbl.set_halign(Gtk.Align.START)
        self.title_lbl.set_xalign(0.0)
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_lines(1)
        self.title_lbl.set_single_line_mode(True)
        text_vbox.append(self.title_lbl)

        # Subtitle Row: Excerpt + Category pill
        subtitle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        subtitle_box.set_hexpand(True)

        raw_excerpt = self.note.excerpt or "No additional text"
        clean_excerpt = strip_markdown(raw_excerpt) or "No additional text"
        self.excerpt_lbl = Gtk.Label(label=clean_excerpt)
        self.excerpt_lbl.add_css_class("subtitle")
        self.excerpt_lbl.set_halign(Gtk.Align.START)
        self.excerpt_lbl.set_xalign(0.0)
        self.excerpt_lbl.set_hexpand(True)
        self.excerpt_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.excerpt_lbl.set_lines(1)
        self.excerpt_lbl.set_single_line_mode(True)
        subtitle_box.append(self.excerpt_lbl)

        if self.note.category and self.show_category_pill:
            self.cat_pill = Gtk.Label(label=self.note.category)
            self.cat_pill.add_css_class("index-category-pill")
            self.cat_pill.set_halign(Gtk.Align.END)
            self.cat_pill.set_ellipsize(Pango.EllipsizeMode.END)
            self.cat_pill.set_lines(1)
            subtitle_box.append(self.cat_pill)

        text_vbox.append(subtitle_box)
        box.append(text_vbox)

        self.set_child(box)

    def _setup_context_menu(self):
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)  # Secondary / Right click

        def on_pressed(_g, _n, _x, _y):
            menu = Gio.Menu()
            pin_label = "Unpin Note" if self.note.is_pinned else "Pin to Top"
            menu.append(pin_label, f"row.pin::{self.note.id}")
            menu.append("Duplicate", f"row.duplicate::{self.note.id}")

            if self.note.is_trashed:
                menu.append("Restore Note", f"row.restore::{self.note.id}")
                menu.append("Delete Permanently", f"row.perm_delete::{self.note.id}")
            else:
                menu.append("Move to Trash", f"row.trash::{self.note.id}")

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(self)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup.new()

            act_pin = Gio.SimpleAction.new("pin", GLib.VariantType.new("s"))
            act_pin.connect("activate", lambda _a, p: self.emit("pin-toggled", p.get_string()))
            action_group.add_action(act_pin)

            act_dup = Gio.SimpleAction.new("duplicate", GLib.VariantType.new("s"))
            act_dup.connect("activate", lambda _a, p: self.emit("duplicate", p.get_string()))
            action_group.add_action(act_dup)

            act_trash = Gio.SimpleAction.new("trash", GLib.VariantType.new("s"))
            act_trash.connect("activate", lambda _a, p: self.emit("delete", p.get_string()))
            action_group.add_action(act_trash)

            act_res = Gio.SimpleAction.new("restore", GLib.VariantType.new("s"))
            act_res.connect("activate", lambda _a, p: self.emit("restore", p.get_string()))
            action_group.add_action(act_res)

            act_perm = Gio.SimpleAction.new("perm_delete", GLib.VariantType.new("s"))
            act_perm.connect("activate", lambda _a, p: self.emit("perm-delete", p.get_string()))
            action_group.add_action(act_perm)

            self.insert_action_group("row", action_group)
            popover.popup()

        gesture.connect("pressed", on_pressed)
        self.add_controller(gesture)

    def set_selection_mode(self, enabled: bool):
        self.revealer.set_reveal_child(enabled)

    def is_checked(self) -> bool:
        return self.checkbox.get_active()

    def set_checked(self, checked: bool):
        self.checkbox.set_active(checked)


# Alias for compatibility
NoteRow = IndexRow


class NotesList(Gtk.Box):
    __gtype_name__ = "NotesList"

    __gsignals__ = {
        "note-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "note-pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-duplicated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-note-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "selection-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.selection_mode = False
        self.current_notes: List[Note] = []
        self._all_rows: List[IndexRow] = []

        self._build_ui()

    def _build_ui(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Scrolled Sectioned View
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(540)

        # Sections Container
        self.sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.sections_box.set_name("Sections")
        self.sections_box.set_margin_top(16)
        self.sections_box.set_margin_bottom(28)
        self.sections_box.set_margin_start(12)
        self.sections_box.set_margin_end(12)

        # 1. Favorites Section
        self.fav_section, self.fav_listbox = self._create_section("Favorites", has_star=True)
        self.sections_box.append(self.fav_section)

        # 2. Today Section
        self.today_section, self.today_listbox = self._create_section("Today")
        self.sections_box.append(self.today_section)

        # 3. Yesterday Section
        self.yesterday_section, self.yesterday_listbox = self._create_section("Yesterday")
        self.sections_box.append(self.yesterday_section)

        # 4. This Week Section
        self.week_section, self.week_listbox = self._create_section("This Week")
        self.sections_box.append(self.week_section)

        # 5. This Month Section
        self.month_section, self.month_listbox = self._create_section("This Month")
        self.sections_box.append(self.month_section)

        # 6. Earlier Section
        self.earlier_section, self.earlier_listbox = self._create_section("Earlier")
        self.sections_box.append(self.earlier_section)

        # 7. Search Results Section (no header)
        self.search_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search_listbox = Gtk.ListBox()
        self.search_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.search_listbox.set_activate_on_single_click(True)
        self.search_listbox.add_css_class("boxed-list")
        self.search_listbox.connect("row-activated", self._on_row_activated)
        self.search_section.append(self.search_listbox)
        self.sections_box.append(self.search_section)

        clamp.set_child(self.sections_box)
        self.scrolled.set_child(clamp)
        self.stack.add_named(self.scrolled, "list")

        # 2. Empty Status Page
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_title("Note List Empty")
        self.empty_page.set_description("Capture your ideas, checklists, and notes in markdown.")
        self.empty_page.set_icon_name("text-justify-fill-symbolic")

        new_btn = Gtk.Button(label="New Note")
        new_btn.add_css_class("pill")
        new_btn.add_css_class("suggested-action")
        new_btn.set_halign(Gtk.Align.CENTER)
        new_btn.connect("clicked", lambda _b: self.emit("new-note-requested"))
        self.empty_page.set_child(new_btn)
        self.stack.add_named(self.empty_page, "empty")

        # 3. Search Empty Page
        self.search_empty_page = Adw.StatusPage()
        self.search_empty_page.set_title("No Results Found")
        self.search_empty_page.set_description("Try searching with different keywords.")
        self.search_empty_page.set_icon_name("system-search-symbolic")
        self.stack.add_named(self.search_empty_page, "search_empty")

        self.append(self.stack)

    def _create_section(self, title: str, has_star: bool = False):
        sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("index-section-title")
        lbl.add_css_class("heading")
        lbl.add_css_class("h4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_xalign(0.0)
        lbl.set_single_line_mode(True)
        lbl.set_lines(1)
        header_box.append(lbl)

        if has_star:
            star_img = Gtk.Image.new_from_icon_name("starred-symbolic")
            star_img.add_css_class("index-section")
            star_img.add_css_class("dimmed")
            star_img.set_pixel_size(16)
            star_img.set_valign(Gtk.Align.CENTER)
            header_box.append(star_img)

        sec_box.append(header_box)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.set_activate_on_single_click(True)
        listbox.add_css_class("boxed-list")
        listbox.connect("row-activated", self._on_row_activated)
        sec_box.append(listbox)

        return sec_box, listbox

    def _clear_listbox(self, listbox: Gtk.ListBox):
        listbox.remove_all()

    def set_notes(
        self,
        notes: List[Note],
        is_search: bool = False,
        active_filter_type: str = "all",
        active_category_name: str = ""
    ):
        self.current_notes = notes
        self._all_rows.clear()

        # Clear all section listboxes
        for lb in [
            self.fav_listbox,
            self.today_listbox,
            self.yesterday_listbox,
            self.week_listbox,
            self.month_listbox,
            self.earlier_listbox,
            self.search_listbox
        ]:
            self._clear_listbox(lb)

        if not notes:
            if is_search:
                self.stack.set_visible_child_name("search_empty")
            else:
                self.stack.set_visible_child_name("empty")
            return

        self.stack.set_visible_child_name("list")
        show_pill = (active_filter_type != "category")

        if is_search:
            # Hide all date sections, populate search section
            self.fav_section.set_visible(False)
            self.today_section.set_visible(False)
            self.yesterday_section.set_visible(False)
            self.week_section.set_visible(False)
            self.month_section.set_visible(False)
            self.earlier_section.set_visible(False)
            self.search_section.set_visible(True)

            for note in notes:
                row = self._create_row(note, show_category_pill=show_pill)
                self.search_listbox.append(row)
            return

        # Regular chronological section grouping
        self.search_section.set_visible(False)

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        yesterday_start = today_start - 86400
        week_start = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())).timestamp()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

        # Favorites bucket
        fav_notes = [n for n in notes if n.is_pinned]
        non_fav_notes = [n for n in notes if not n.is_pinned]

        today_notes = []
        yesterday_notes = []
        week_notes = []
        month_notes = []
        earlier_notes = []

        for n in non_fav_notes:
            t = n.updated_at
            if t >= today_start:
                today_notes.append(n)
            elif t >= yesterday_start:
                yesterday_notes.append(n)
            elif t >= week_start:
                week_notes.append(n)
            elif t >= month_start:
                month_notes.append(n)
            else:
                earlier_notes.append(n)

        sections_data = [
            (self.fav_section, self.fav_listbox, fav_notes),
            (self.today_section, self.today_listbox, today_notes),
            (self.yesterday_section, self.yesterday_listbox, yesterday_notes),
            (self.week_section, self.week_listbox, week_notes),
            (self.month_section, self.month_listbox, month_notes),
            (self.earlier_section, self.earlier_listbox, earlier_notes),
        ]

        for sec_widget, listbox, n_list in sections_data:
            if n_list:
                sec_widget.set_visible(True)
                for note in n_list:
                    row = self._create_row(note, show_category_pill=show_pill)
                    listbox.append(row)
            else:
                sec_widget.set_visible(False)

    def _create_row(self, note: Note, show_category_pill: bool = True) -> IndexRow:
        row = IndexRow(note, selection_mode=self.selection_mode, show_category_pill=show_category_pill)
        row.connect("pin-toggled", lambda _r, nid: self.emit("note-pin-toggled", nid))
        row.connect("duplicate", lambda _r, nid: self.emit("note-duplicated", nid))
        row.connect("delete", lambda _r, nid: self.emit("note-deleted", nid))
        row.connect("restore", lambda _r, nid: self._on_restore(nid))
        row.connect("perm-delete", lambda _r, nid: self._on_perm_delete(nid))
        row.connect("toggled", lambda _r, _a: self.emit("selection-changed", len(self.get_checked_notes())))
        self._all_rows.append(row)
        return row

    def _on_restore(self, note_id: str):
        self.db.restore_note(note_id)
        self.emit("note-pin-toggled", note_id)

    def _on_perm_delete(self, note_id: str):
        self.db.delete_note(note_id, permanent=True)
        self.emit("note-pin-toggled", note_id)

    def _on_row_activated(self, _lb, row: IndexRow):
        if not row:
            return
        if self.selection_mode:
            row.set_checked(not row.is_checked())
        else:
            self.emit("note-selected", row.note)

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        for row in self._all_rows:
            row.set_selection_mode(enabled)
            if not enabled:
                row.set_checked(False)
        if not enabled:
            self.emit("selection-changed", 0)

    def get_checked_notes(self) -> List[Note]:
        return [row.note for row in self._all_rows if row.is_checked()]

    def select_all(self, checked: bool = True):
        for row in self._all_rows:
            row.set_checked(checked)
        self.emit("selection-changed", len(self.get_checked_notes()))

    def clear_all_checkboxes(self):
        for row in self._all_rows:
            row.set_checked(False)
        self.emit("selection-changed", 0)

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Optional
from gi.repository import Adw, Gtk, Gdk, Gio, GLib, GObject, Pango

from stilonotes.models import Note
from stilonotes.markdown_utils import strip_markdown


def get_note_image_bytes(note: Note, db=None) -> Optional[bytes]:
    """Retrieve raw image bytes for preview if note has an image."""
    # 1. First check database attachments for this note if db is available
    if db and hasattr(db, "get_note_first_image"):
        try:
            data = db.get_note_first_image(note.id)
            if data:
                return data
        except Exception:
            pass

    # 2. Check for attachment://<id>, data:image, file:// in markdown or html
    content = ""
    if note.content_markdown:
        content += note.content_markdown + "\n"
    if note.content_html:
        content += note.content_html

    if not content:
        return None

    # Check for markdown image ![alt](url)
    md_match = re.search(r'!\[.*?\]\((.+?)\)', content)
    url = ""
    if md_match:
        url = md_match.group(1).strip().split()[0]
    else:
        # Check for HTML img tag
        html_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if html_match:
            url = html_match.group(1).strip()

    if not url:
        return None

    # Resolve url
    if url.startswith("attachment://") or url.startswith("attachment:"):
        prefix = "attachment://" if url.startswith("attachment://") else "attachment:"
        att_id = url[len(prefix):].split("/")[0].split("?")[0].split("#")[0]
        if db and hasattr(db, "get_attachment"):
            try:
                att = db.get_attachment(att_id)
                if att and att.get("data"):
                    return att["data"]
                if "." in att_id:
                    att = db.get_attachment(att_id.rsplit(".", 1)[0])
                    if att and att.get("data"):
                        return att["data"]
            except Exception:
                pass

    elif url.startswith("data:image/") and ";base64," in url:
        try:
            b64_part = url.split(";base64,", 1)[1]
            return base64.b64decode(b64_part)
        except Exception:
            pass

    elif url.startswith("file://") or (url.startswith("/") and os.path.isabs(url)):
        local_path = url[len("file://"):] if url.startswith("file://") else url
        local_path = urllib.parse.unquote(local_path)
        if os.path.isfile(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception:
                pass

    return None


def _create_thumbnail_texture(img_bytes: bytes) -> Optional[Gdk.Texture]:
    """Create a bounded Gdk.Texture from image bytes, scaled and center-cropped to 216x80."""
    try:
        import gi
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        loader = GdkPixbuf.PixbufLoader()
        loader.write(img_bytes)
        loader.close()
        pix = loader.get_pixbuf()
        if pix:
            target_w, target_h = 216, 80
            w, h = pix.get_width(), pix.get_height()
            if w > 0 and h > 0:
                scale = max(target_w / w, target_h / h)
                scaled_w = max(target_w, int(w * scale))
                scaled_h = max(target_h, int(h * scale))
                pix_scaled = pix.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)
                if pix_scaled:
                    src_x = max(0, (scaled_w - target_w) // 2)
                    src_y = max(0, (scaled_h - target_h) // 2)
                    pix_cropped = GdkPixbuf.Pixbuf.new(
                        GdkPixbuf.Colorspace.RGB,
                        pix.get_has_alpha(),
                        8,
                        target_w,
                        target_h
                    )
                    pix_scaled.copy_area(src_x, src_y, target_w, target_h, pix_cropped, 0, 0)
                    success, buf = pix_cropped.save_to_bufferv("png", [], [])
                    if success:
                        return Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf))
    except Exception:
        pass
    return None


def _get_note_preview(note: Note) -> str:
    """Extract clean multi-line preview text from note markdown or excerpt."""
    text = ""
    if note.content_markdown:
        lines = note.content_markdown.splitlines()
        if lines and lines[0].strip().lstrip("#").strip() == (note.title or "").strip():
            text = "\n".join(lines[1:]).strip()
        else:
            text = note.content_markdown.strip()
    if not text:
        text = note.excerpt or ""
    # Strip markdown and html image tags so they don't leak into excerpt text
    text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
    text = re.sub(r'<img[^>]+>', '', text)
    clean = strip_markdown(text).strip()
    return clean if clean else "Type text here..."


class BaseNoteCard(Gtk.FlowBoxChild):
    __gtype_name__ = "BaseNoteCard"

    __gsignals__ = {
        "pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplicate": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "restore": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "perm-delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, note: Note, db=None, selection_mode: bool = False, show_category_pill: bool = True):
        super().__init__()
        self.note = note
        self.db = db
        self.show_category_pill = show_category_pill
        self.card_box: Optional[Gtk.Box] = None
        self.revealer: Optional[Gtk.Revealer] = None
        self.checkbox: Optional[Gtk.CheckButton] = None

        self._build_ui(selection_mode)
        self._setup_context_menu()

    def _build_ui(self, selection_mode: bool):
        raise NotImplementedError

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
        if self.revealer:
            self.revealer.set_reveal_child(enabled)

    def is_checked(self) -> bool:
        return self.checkbox.get_active() if self.checkbox else False

    def set_checked(self, checked: bool):
        if self.checkbox:
            self.checkbox.set_active(checked)
        if self.card_box:
            if checked:
                self.card_box.add_css_class("checked")
            else:
                self.card_box.remove_css_class("checked")


class NoteGridCard(BaseNoteCard):
    __gtype_name__ = "NoteGridCard"

    def _build_ui(self, selection_mode: bool):
        self.set_size_request(240, 220)
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self.card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.card_box.add_css_class("note-grid-card")
        self.card_box.set_size_request(240, 220)
        self.card_box.set_hexpand(True)
        self.card_box.set_vexpand(True)
        self.card_box.set_halign(Gtk.Align.FILL)
        self.card_box.set_valign(Gtk.Align.FILL)
        self.card_box.set_overflow(Gtk.Overflow.HIDDEN)

        # 1. Top Row: Checkbox revealer + Dot + Title + (Pin/Todo Icons)
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top_box.set_hexpand(True)

        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_reveal_child(selection_mode)

        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.connect("toggled", self._on_checkbox_toggled)
        self.revealer.set_child(self.checkbox)
        top_box.append(self.revealer)

        # Category Dot indicator (Image 1 style)
        dot = Gtk.Box()
        dot.add_css_class("note-dot")
        dot.set_valign(Gtk.Align.CENTER)
        dot.set_halign(Gtk.Align.CENTER)
        if self.note.category:
            c_idx = abs(hash(self.note.category)) % 9
            dot.add_css_class(f"cat-{c_idx}")
        top_box.append(dot)

        # Title
        raw_title = self.note.title or "Untitled Note"
        clean_title = strip_markdown(raw_title) or "Untitled Note"
        self.title_lbl = Gtk.Label(label=clean_title)
        self.title_lbl.add_css_class("note-grid-title")
        self.title_lbl.set_halign(Gtk.Align.START)
        self.title_lbl.set_xalign(0.0)
        self.title_lbl.set_hexpand(True)
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_lines(1)
        self.title_lbl.set_single_line_mode(True)
        top_box.append(self.title_lbl)

        if self.note.is_pinned:
            pin_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            pin_icon.add_css_class("dimmed")
            pin_icon.set_pixel_size(14)
            top_box.append(pin_icon)

        if self.note.has_todo:
            todo_icon = Gtk.Image.new_from_icon_name("checklist-symbolic")
            todo_icon.add_css_class("dimmed")
            todo_icon.set_pixel_size(14)
            top_box.append(todo_icon)

        self.card_box.append(top_box)

        # 2. Date Row: "Monday, 28/09 08:02" (matching Image 1)
        try:
            dt = datetime.fromtimestamp(self.note.updated_at)
            date_str = dt.strftime("%A, %d/%m %H:%M")
        except Exception:
            date_str = ""

        if date_str:
            self.date_lbl = Gtk.Label(label=date_str)
            self.date_lbl.add_css_class("note-grid-date")
            self.date_lbl.set_halign(Gtk.Align.START)
            self.date_lbl.set_xalign(0.0)
            self.date_lbl.set_lines(1)
            self.date_lbl.set_single_line_mode(True)
            self.date_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            self.card_box.append(self.date_lbl)

        # 3. Thumbnail Image Banner (BELOW TITLE AND DATE!)
        img_bytes = get_note_image_bytes(self.note, self.db)
        self.thumb = None
        if img_bytes:
            texture = _create_thumbnail_texture(img_bytes)
            if texture:
                img_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                img_container.set_size_request(216, 80)
                img_container.set_hexpand(False)
                img_container.set_vexpand(False)
                img_container.set_halign(Gtk.Align.CENTER)
                img_container.set_valign(Gtk.Align.CENTER)
                img_container.set_overflow(Gtk.Overflow.HIDDEN)

                self.thumb = Gtk.Picture.new_for_paintable(texture)
                self.thumb.set_can_shrink(True)
                self.thumb.set_content_fit(Gtk.ContentFit.COVER)
                self.thumb.set_size_request(216, 80)
                self.thumb.add_css_class("note-grid-thumbnail")
                img_container.append(self.thumb)
                self.card_box.append(img_container)

        # 4. Body excerpt preview (multi-line)
        preview_text = _get_note_preview(self.note)
        self.body_lbl = Gtk.Label(label=preview_text)
        self.body_lbl.add_css_class("note-grid-body")
        self.body_lbl.set_wrap(True)
        self.body_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.body_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.body_lbl.set_lines(2 if self.thumb else 5)
        self.body_lbl.set_halign(Gtk.Align.START)
        self.body_lbl.set_valign(Gtk.Align.START)
        self.body_lbl.set_xalign(0.0)
        self.body_lbl.set_yalign(0.0)
        self.body_lbl.set_vexpand(True)
        self.card_box.append(self.body_lbl)

        # 5. Bottom Row: Category pill (anchored to bottom)
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer_box.set_valign(Gtk.Align.END)
        footer_box.set_halign(Gtk.Align.START)
        footer_box.set_vexpand(False)

        if self.note.category and self.show_category_pill:
            pill = Gtk.Label(label=self.note.category)
            pill.add_css_class("index-category-pill")
            pill.set_ellipsize(Pango.EllipsizeMode.END)
            pill.set_lines(1)
            pill.set_single_line_mode(True)
            footer_box.append(pill)

        self.card_box.append(footer_box)

        self.set_child(self.card_box)

    def _on_checkbox_toggled(self, cb):
        active = cb.get_active()
        if active:
            self.card_box.add_css_class("checked")
        else:
            self.card_box.remove_css_class("checked")
        self.emit("toggled", active)


class NoteListRow(BaseNoteCard):
    __gtype_name__ = "NoteListRow"

    def _build_ui(self, selection_mode: bool):
        self.set_size_request(340, 72)
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        self.card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.card_box.add_css_class("note-list-card")
        self.card_box.set_hexpand(True)

        # Checkbox revealer for selection mode
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_reveal_child(selection_mode)

        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.set_margin_end(8)
        self.checkbox.connect("toggled", self._on_checkbox_toggled)
        self.revealer.set_child(self.checkbox)
        self.card_box.append(self.revealer)

        # Note text column
        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_vbox.set_hexpand(True)
        text_vbox.set_valign(Gtk.Align.CENTER)

        # Title row: Title Label + Starred Icon
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        raw_title = self.note.title or "Untitled Note"
        clean_title = strip_markdown(raw_title) or "Untitled Note"
        self.title_lbl = Gtk.Label(label=clean_title)
        self.title_lbl.add_css_class("title")
        self.title_lbl.set_halign(Gtk.Align.START)
        self.title_lbl.set_xalign(0.0)
        self.title_lbl.set_hexpand(True)
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_lines(1)
        self.title_lbl.set_single_line_mode(True)
        title_box.append(self.title_lbl)

        if self.note.is_pinned:
            pin_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            pin_icon.add_css_class("dimmed")
            pin_icon.set_pixel_size(14)
            title_box.append(pin_icon)

        text_vbox.append(title_box)

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
        self.card_box.append(text_vbox)

        self.set_child(self.card_box)

    def _on_checkbox_toggled(self, cb):
        active = cb.get_active()
        if active:
            self.card_box.add_css_class("checked")
        else:
            self.card_box.remove_css_class("checked")
        self.emit("toggled", active)


# Aliases for compatibility
IndexRow = NoteListRow
NoteRow = NoteListRow


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

    def __init__(self, db, view_mode: str = "list"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.view_mode = view_mode
        self.selection_mode = False
        self.current_notes: List[Note] = []
        self._all_cards: List[BaseNoteCard] = []
        self.is_search = False
        self.active_filter_type = "all"
        self.active_category_name = ""

        self._build_ui()

    @property
    def _all_rows(self) -> List[BaseNoteCard]:
        return self._all_cards

    @_all_rows.setter
    def _all_rows(self, val):
        self._all_cards = val

    def _build_ui(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Scrolled Sectioned View
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)

        self.clamp = Adw.Clamp()
        self.clamp.set_maximum_size(2400)
        self.clamp.set_tightening_threshold(1600)

        # Sections Container
        self.sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.sections_box.set_name("Sections")
        self.sections_box.set_margin_top(16)
        self.sections_box.set_margin_bottom(28)
        self.sections_box.set_margin_start(16)
        self.sections_box.set_margin_end(16)

        # 1. Favorites Section
        self.fav_section, self.fav_flowbox = self._create_section("Favorites", has_star=True)
        self.sections_box.append(self.fav_section)

        # 2. Today Section
        self.today_section, self.today_flowbox = self._create_section("Today")
        self.sections_box.append(self.today_section)

        # 3. Yesterday Section
        self.yesterday_section, self.yesterday_flowbox = self._create_section("Yesterday")
        self.sections_box.append(self.yesterday_section)

        # 4. This Week Section
        self.week_section, self.week_flowbox = self._create_section("This Week")
        self.sections_box.append(self.week_section)

        # 5. This Month Section
        self.month_section, self.month_flowbox = self._create_section("This Month")
        self.sections_box.append(self.month_section)

        # 6. Earlier Section
        self.earlier_section, self.earlier_flowbox = self._create_section("Earlier")
        self.sections_box.append(self.earlier_section)

        # 7. Search Results Section (no header)
        self.search_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search_flowbox = self._create_flowbox()
        self.search_section.append(self.search_flowbox)
        self.sections_box.append(self.search_section)

        self.clamp.set_child(self.sections_box)
        self.scrolled.set_child(self.clamp)
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

    def _get_spacing(self):
        col_spacing = 8 if self.view_mode == "grid" else 6
        row_spacing = 8 if self.view_mode == "grid" else 6
        return col_spacing, row_spacing

    def _create_flowbox(self) -> Gtk.FlowBox:
        flowbox = Gtk.FlowBox()
        flowbox.set_homogeneous(True)
        flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flowbox.set_activate_on_single_click(True)
        col_sp, row_sp = self._get_spacing()
        flowbox.set_column_spacing(col_sp)
        flowbox.set_row_spacing(row_sp)
        flowbox.set_min_children_per_line(1)
        flowbox.set_max_children_per_line(24)
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_halign(Gtk.Align.FILL if self.view_mode == "list" else Gtk.Align.START)
        flowbox.set_hexpand(True)
        flowbox.add_css_class("notes-flowbox")
        flowbox.connect("child-activated", self._on_child_activated)
        return flowbox

    def _create_section(self, title: str, has_star: bool = False):
        sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

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

        flowbox = self._create_flowbox()
        sec_box.append(flowbox)

        return sec_box, flowbox

    def set_view_mode(self, mode: str):
        if mode not in ("list", "grid"):
            mode = "list"
        if self.view_mode != mode:
            self.view_mode = mode
            col_sp, row_sp = self._get_spacing()
            for fb in [
                self.fav_flowbox,
                self.today_flowbox,
                self.yesterday_flowbox,
                self.week_flowbox,
                self.month_flowbox,
                self.earlier_flowbox,
                self.search_flowbox
            ]:
                fb.set_column_spacing(col_sp)
                fb.set_row_spacing(row_sp)
                fb.set_halign(Gtk.Align.FILL if mode == "list" else Gtk.Align.START)
            self.set_notes(
                self.current_notes,
                is_search=self.is_search,
                active_filter_type=self.active_filter_type,
                active_category_name=self.active_category_name
            )

    def _clear_flowbox(self, flowbox: Gtk.FlowBox):
        flowbox.remove_all()

    def set_notes(
        self,
        notes: List[Note],
        is_search: bool = False,
        active_filter_type: str = "all",
        active_category_name: str = ""
    ):
        self.current_notes = notes
        self.is_search = is_search
        self.active_filter_type = active_filter_type
        self.active_category_name = active_category_name
        self._all_cards.clear()

        # Clear all section flowboxes
        for fb in [
            self.fav_flowbox,
            self.today_flowbox,
            self.yesterday_flowbox,
            self.week_flowbox,
            self.month_flowbox,
            self.earlier_flowbox,
            self.search_flowbox
        ]:
            self._clear_flowbox(fb)

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
                card = self._create_card(note, show_category_pill=show_pill)
                self.search_flowbox.append(card)
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
            (self.fav_section, self.fav_flowbox, fav_notes),
            (self.today_section, self.today_flowbox, today_notes),
            (self.yesterday_section, self.yesterday_flowbox, yesterday_notes),
            (self.week_section, self.week_flowbox, week_notes),
            (self.month_section, self.month_flowbox, month_notes),
            (self.earlier_section, self.earlier_flowbox, earlier_notes),
        ]

        for sec_widget, flowbox, n_list in sections_data:
            if n_list:
                sec_widget.set_visible(True)
                for note in n_list:
                    card = self._create_card(note, show_category_pill=show_pill)
                    flowbox.append(card)
            else:
                sec_widget.set_visible(False)

    def _create_card(self, note: Note, show_category_pill: bool = True) -> BaseNoteCard:
        if self.view_mode == "grid":
            card = NoteGridCard(note, db=self.db, selection_mode=self.selection_mode, show_category_pill=show_category_pill)
        else:
            card = NoteListRow(note, db=self.db, selection_mode=self.selection_mode, show_category_pill=show_category_pill)

        card.connect("pin-toggled", lambda _r, nid: self.emit("note-pin-toggled", nid))
        card.connect("duplicate", lambda _r, nid: self.emit("note-duplicated", nid))
        card.connect("delete", lambda _r, nid: self.emit("note-deleted", nid))
        card.connect("restore", lambda _r, nid: self._on_restore(nid))
        card.connect("perm-delete", lambda _r, nid: self._on_perm_delete(nid))
        card.connect("toggled", lambda _r, _a: self.emit("selection-changed", len(self.get_checked_notes())))
        self._all_cards.append(card)
        return card

    def _create_row(self, note: Note, show_category_pill: bool = True) -> BaseNoteCard:
        """Alias for backward compatibility."""
        return self._create_card(note, show_category_pill=show_category_pill)

    def _on_restore(self, note_id: str):
        self.db.restore_note(note_id)
        self.emit("note-pin-toggled", note_id)

    def _on_perm_delete(self, note_id: str):
        self.db.delete_note(note_id, permanent=True)
        self.emit("note-pin-toggled", note_id)

    def _on_child_activated(self, flowbox: Gtk.FlowBox, child: BaseNoteCard):
        if not child:
            return
        flowbox.unselect_all()
        if self.selection_mode:
            child.set_checked(not child.is_checked())
        else:
            self.emit("note-selected", child.note)

    def _on_row_activated(self, flowbox, child):
        """Alias for backward compatibility."""
        self._on_child_activated(flowbox, child)

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        for card in self._all_cards:
            card.set_selection_mode(enabled)
            if not enabled:
                card.set_checked(False)
        if not enabled:
            self.emit("selection-changed", 0)

    def get_checked_notes(self) -> List[Note]:
        return [card.note for card in self._all_cards if card.is_checked()]

    def select_all(self, checked: bool = True):
        for card in self._all_cards:
            card.set_checked(checked)
        self.emit("selection-changed", len(self.get_checked_notes()))

    def clear_all_checkboxes(self):
        for card in self._all_cards:
            card.set_checked(False)
        self.emit("selection-changed", 0)

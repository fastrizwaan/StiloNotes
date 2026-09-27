# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import base64
import mimetypes
import threading
from pathlib import Path
from typing import Optional

import gi
gi.require_version('WebKit', '6.0')
from gi.repository import Adw, Gtk, WebKit, Gio, GLib, GObject, Gdk, Pango

from stilonotes.category_header_bar import CategoryHeaderBar
from stilonotes.config_manager import ConfigManager
from stilonotes.theme_selector import ThemeSelector
from stilonotes.font_size_selector import FontSizeSelector
from stilonotes.models import Note
from stilonotes.editor_html import get_editor_html_page
from stilonotes.markdown_utils import compute_note_stats, format_relative_date, html_to_markdown, markdown_to_html
from stilonotes.exporter import export_note_dialog
from stilonotes.const import get_assets_path

_GLOBAL_DB = None
_URI_SCHEME_REGISTERED = False


def _register_attachment_scheme(db):
    """Register custom attachment:// URI scheme with WebKit to serve images from SQLite BLOBs."""
    global _GLOBAL_DB, _URI_SCHEME_REGISTERED
    _GLOBAL_DB = db
    if _URI_SCHEME_REGISTERED:
        return
    try:
        ctx = WebKit.WebContext.get_default()

        def handle_attachment(request):
            try:
                uri = request.get_uri()
                path = uri
                if path.startswith("attachment://"):
                    path = path[len("attachment://"):]
                elif path.startswith("attachment:"):
                    path = path[len("attachment:"):]
                att_id = path.split("/")[0].split("?")[0].split("#")[0]
                if _GLOBAL_DB:
                    att = _GLOBAL_DB.get_attachment(att_id)
                    if not att and "." in att_id:
                        att = _GLOBAL_DB.get_attachment(att_id.rsplit(".", 1)[0])

                    if att and att.get("data"):
                        data = att["data"]
                        mime = att.get("mime_type") or "image/png"
                        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data))
                        request.finish(stream, len(data), mime)
                        return
            except Exception as e:
                print("Attachment URI scheme error:", e)

            err = GLib.Error.new_literal(Gio.io_error_quark(), "Attachment not found", int(Gio.IOErrorEnum.NOT_FOUND))
            request.finish_error(err)

        ctx.register_uri_scheme("attachment", handle_attachment)
        _URI_SCHEME_REGISTERED = True
    except Exception as e:
        print("Failed to register attachment URI scheme:", e)


class FormattingBar(Gtk.Box):
    """Bottom formatting toolbar — mirrors Iotas FormattingHeaderBar style."""

    __gtype_name__ = "StiloFormattingBar"

    def __init__(self, exec_fn, insert_table_fn=None, pick_image_fn=None, toggle_pin_fn=None, is_pinned=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._exec = exec_fn
        self._insert_table = insert_table_fn
        self._pick_image = pick_image_fn
        self._toggle_pin = toggle_pin_fn
        self._is_pinned = is_pinned
        self.h_pop = None
        self.table_pop = None
        self.pin_btn = None
        self._build()

    def is_popover_open(self) -> bool:
        h_open = bool(self.h_pop and self.h_pop.get_visible())
        t_open = bool(self.table_pop and self.table_pop.get_visible())
        return h_open or t_open

    def _build(self):
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(sep)

        hbar = Adw.HeaderBar()
        hbar.set_show_start_title_buttons(False)
        hbar.set_show_end_title_buttons(False)
        hbar.set_show_back_button(False)
        hbar.add_css_class("formatting")
        self.append(hbar)

        parent_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        parent_box.set_halign(Gtk.Align.CENTER)
        hbar.set_title_widget(parent_box)

        # 0. Undo & Redo
        self._add_btn(parent_box, "edit-undo-symbolic", "Undo (Ctrl+Z)", "undo")
        self._add_btn(parent_box, "edit-redo-symbolic", "Redo (Ctrl+Y)", "redo")
        self._add_sep(parent_box)

        # 1. Heading menu button
        heading_menu = Gtk.MenuButton()
        heading_menu.set_icon_name("format-text-larger-symbolic")
        heading_menu.set_tooltip_text("Heading")
        heading_menu.set_focus_on_click(False)
        heading_menu.add_css_class("flat")

        self.h_pop = Gtk.Popover()
        h_pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h_pop_box.set_margin_start(4)
        h_pop_box.set_margin_end(4)
        h_pop_box.set_margin_top(4)
        h_pop_box.set_margin_bottom(4)
        for lbl, cmd in [("Heading 1", "heading1"), ("Heading 2", "heading2"),
                         ("Heading 3", "heading3"), ("Paragraph", "paragraph")]:
            b = Gtk.Button(label=lbl)
            b.add_css_class("flat")
            b.connect("clicked", lambda _b, c=cmd: (self.h_pop.popdown(), self._exec(c)))
            h_pop_box.append(b)
        self.h_pop.set_child(h_pop_box)
        heading_menu.set_popover(self.h_pop)
        parent_box.append(heading_menu)

        self._add_sep(parent_box)

        # 2. Text styling
        for icon, tip, cmd in [
            ("format-text-bold-symbolic",          "Bold",          "bold"),
            ("format-text-italic-symbolic",        "Italic",        "italic"),
            ("format-text-strikethrough-symbolic", "Strikethrough", "strike"),
            ("format-text-underline-symbolic",     "Underline",     "underline"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

        self._add_sep(parent_box)

        # 3. Lists
        for icon, tip, cmd in [
            ("view-list-bullet-symbolic",  "Bullet List",   "bullet"),
            ("view-list-ordered-symbolic", "Numbered List", "number"),
            ("checkbox-checked-symbolic",  "Checklist",     "todo"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

        self._add_sep(parent_box)

        # 4. Blocks & Markdown Elements
        for icon, tip, cmd in [
            ("quotation-symbolic",       "Blockquote",      "quote"),
            ("code-symbolic",            "Code Block",      "code"),
            ("insert-link-symbolic",     "Insert Link",     "link"),
            ("view-continuous-symbolic", "Horizontal Rule", "divider"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

        self._add_sep(parent_box)

        # 5. Insert Table menu button with popover
        table_menu = Gtk.MenuButton()
        table_menu.set_icon_name("insert-table-symbolic")
        table_menu.set_tooltip_text("Table")
        table_menu.set_focus_on_click(False)
        table_menu.add_css_class("flat")

        self.table_pop = Gtk.Popover()
        pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pop_box.set_margin_start(12)
        pop_box.set_margin_end(12)
        pop_box.set_margin_top(10)
        pop_box.set_margin_bottom(10)

        title_lbl = Gtk.Label(label="Insert Table")
        title_lbl.add_css_class("heading")
        title_lbl.set_halign(Gtk.Align.START)
        pop_box.append(title_lbl)

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(12)

        lbl_r = Gtk.Label(label="Rows:")
        lbl_r.set_halign(Gtk.Align.START)
        spin_r = Gtk.SpinButton.new_with_range(1, 20, 1)
        spin_r.set_value(3)
        grid.attach(lbl_r, 0, 0, 1, 1)
        grid.attach(spin_r, 1, 0, 1, 1)

        lbl_c = Gtk.Label(label="Columns:")
        lbl_c.set_halign(Gtk.Align.START)
        spin_c = Gtk.SpinButton.new_with_range(1, 10, 1)
        spin_c.set_value(3)
        grid.attach(lbl_c, 0, 1, 1, 1)
        grid.attach(spin_c, 1, 1, 1, 1)

        pop_box.append(grid)

        chk_hdr = Gtk.CheckButton(label="Include header row")
        chk_hdr.set_active(True)
        pop_box.append(chk_hdr)

        btn_insert = Gtk.Button(label="Insert Table")
        btn_insert.add_css_class("suggested-action")

        def on_insert_tbl(_b):
            r = int(spin_r.get_value())
            c = int(spin_c.get_value())
            h = chk_hdr.get_active()
            self.table_pop.popdown()
            if self._insert_table:
                self._insert_table(r, c, h)
            else:
                self._exec("table")

        btn_insert.connect("clicked", on_insert_tbl)
        pop_box.append(btn_insert)

        # Quick edit table actions separator
        sep_tbl = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_tbl.set_margin_top(4)
        sep_tbl.set_margin_bottom(4)
        pop_box.append(sep_tbl)

        edit_lbl = Gtk.Label(label="Edit Active Table")
        edit_lbl.add_css_class("dim-label")
        edit_lbl.set_halign(Gtk.Align.START)
        pop_box.append(edit_lbl)

        btn_row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_add_row = Gtk.Button(label="+ Row")
        btn_add_row.add_css_class("flat")
        btn_add_row.connect("clicked", lambda _b: (self.table_pop.popdown(), self._exec("table-add-row")))
        btn_del_row = Gtk.Button(label="− Row")
        btn_del_row.add_css_class("flat")
        btn_del_row.connect("clicked", lambda _b: (self.table_pop.popdown(), self._exec("table-del-row")))
        btn_row_box.append(btn_add_row)
        btn_row_box.append(btn_del_row)
        pop_box.append(btn_row_box)

        btn_col_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_add_col = Gtk.Button(label="+ Col")
        btn_add_col.add_css_class("flat")
        btn_add_col.connect("clicked", lambda _b: (self.table_pop.popdown(), self._exec("table-add-col")))
        btn_del_col = Gtk.Button(label="− Col")
        btn_del_col.add_css_class("flat")
        btn_del_col.connect("clicked", lambda _b: (self.table_pop.popdown(), self._exec("table-del-col")))
        btn_col_box.append(btn_add_col)
        btn_col_box.append(btn_del_col)
        pop_box.append(btn_col_box)

        btn_del_tbl = Gtk.Button(label="Delete Table")
        btn_del_tbl.add_css_class("destructive-action")
        btn_del_tbl.connect("clicked", lambda _b: (self.table_pop.popdown(), self._exec("table-delete")))
        pop_box.append(btn_del_tbl)

        self.table_pop.set_child(pop_box)
        table_menu.set_popover(self.table_pop)
        parent_box.append(table_menu)

        # 6. Insert Image button
        img_btn = Gtk.Button()
        img_btn.set_icon_name("insert-image-symbolic")
        img_btn.set_tooltip_text("Insert Image")
        img_btn.set_focus_on_click(False)
        img_btn.add_css_class("flat")
        img_btn.connect("clicked", lambda _b: self._on_image_clicked())
        parent_box.append(img_btn)

        # 7. Pin ToggleButton packed at the end of the headerbar
        self.pin_btn = Gtk.ToggleButton()
        self.pin_btn.set_icon_name("view-pin-symbolic")
        self.pin_btn.set_tooltip_text("Unpin Toolbar (Auto-hide)" if self._is_pinned else "Pin Toolbar (Always visible)")
        self.pin_btn.set_active(self._is_pinned)
        self.pin_btn.set_focus_on_click(False)
        self.pin_btn.add_css_class("flat")
        if self._is_pinned:
            self.pin_btn.add_css_class("stilo-pin-active")
        self.pin_btn.connect("toggled", self._on_pin_toggled)
        hbar.pack_end(self.pin_btn)

    def _on_image_clicked(self):
        if self._pick_image:
            self._pick_image()
        else:
            self._exec("image")

    def _on_pin_toggled(self, btn):
        pinned = btn.get_active()
        self._is_pinned = pinned
        if pinned:
            btn.add_css_class("stilo-pin-active")
            btn.set_tooltip_text("Unpin Toolbar (Auto-hide)")
        else:
            btn.remove_css_class("stilo-pin-active")
            btn.set_tooltip_text("Pin Toolbar (Always visible)")
        if self._toggle_pin:
            self._toggle_pin(pinned)

    def _add_btn(self, box, icon_name, tooltip, cmd):
        btn = Gtk.Button()
        btn.set_icon_name(icon_name)
        btn.set_tooltip_text(tooltip)
        btn.set_focus_on_click(False)
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _b, c=cmd: self._exec(c))
        box.append(btn)
        return btn

    def _add_sep(self, box):
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        box.append(sep)


class NoteEditor(Gtk.Box):
    __gtype_name__ = "NoteEditor"

    __gsignals__ = {
        "note-updated":          (GObject.SignalFlags.RUN_FIRST, None, (str, str, str, str, str, object, bool)),
        "note-deleted":          (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-pin-toggled":      (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-duplicated":       (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-category-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "back":                  (GObject.SignalFlags.RUN_FIRST, None, ()),
        "toggle-app-theme":      (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.config_manager = ConfigManager.get_default(self.db)
        self.current_note: Optional[Note] = None
        style_manager = Adw.StyleManager.get_default()
        self.is_dark_mode = style_manager.get_dark()
        style_manager.connect("notify::dark", lambda sm, _p: self.update_theme(sm.get_dark()))
        self.latest_stats = {"words": 0, "chars": 0, "paragraphs": 0, "readTime": "1 min"}
        self._toolbar_reveal_timeout = None
        self._pending_save_data = None
        self._mouse_over_toolbar = False
        self._mouse_near_bottom = False
        self._is_toolbar_pinned = (self.db.get_setting("toolbar_pinned", "false") == "true")
        self._page_loaded = False
        self._pending_load_note = None
        self._save_timeout_id = None
        self._syncing_format_btn = False
        _register_attachment_scheme(self.db)
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        # Header Stack
        self.header_stack = Gtk.Stack()
        self.header_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.main_header_bar = Adw.HeaderBar()
        self.main_header_bar.set_show_back_button(False)
        self.main_header_bar.set_show_end_title_buttons(True)
        self.main_header_bar.set_show_start_title_buttons(False)

        self.back_btn = Gtk.Button()
        self.back_btn.set_icon_name("go-previous-symbolic")
        self.back_btn.set_tooltip_text("Back to Notes")
        self.back_btn.connect("clicked", lambda _b: self.emit("back"))
        self.main_header_bar.pack_start(self.back_btn)

        self.title_label = Gtk.Label(label="Untitled Note")
        self.title_label.add_css_class("title")
        self.title_label.add_css_class("stilo-editor-title")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(32)
        self.main_header_bar.set_title_widget(self.title_label)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_visible(False)

        # 1. Editor menu (more) - all the way right
        self.more_btn = Gtk.MenuButton()
        self.more_btn.set_icon_name("view-more-symbolic")
        self.more_btn.set_tooltip_text("Editor Menu")
        self.more_btn.set_menu_model(self._create_more_menu())

        more_popover = self.more_btn.get_popover()
        self.theme_selector = ThemeSelector(self.config_manager, on_theme_changed=self.update_theme)
        more_popover.add_child(self.theme_selector, "theme")
        self.font_size_selector = FontSizeSelector(self.config_manager, on_font_size_changed=self.update_font_size)
        more_popover.add_child(self.font_size_selector, "fontsize")

        # 2. Stats button
        self.stats_popover = self._create_stats_popover()
        self.info_btn = Gtk.MenuButton()
        self.info_btn.set_icon_name("dialog-information-symbolic")
        self.info_btn.set_tooltip_text("Note Statistics")
        self.info_btn.set_popover(self.stats_popover)

        # 3. Format Toolbar Toggle button
        self.format_btn = Gtk.ToggleButton()
        self.format_btn.set_icon_name("format-text-bold-symbolic")
        self.format_btn.set_tooltip_text("Toggle Formatting Bar (Ctrl+Shift+F)")
        self.format_btn.set_focus_on_click(False)
        self.format_btn.add_css_class("flat")
        self.format_btn.connect("toggled", self._on_format_btn_toggled)

        # 4. Star / Favorites toggle button
        self.star_btn = Gtk.Button()
        self.star_btn.set_icon_name("non-starred-symbolic")
        self.star_btn.set_tooltip_text("Pin to Favorites")
        self.star_btn.add_css_class("flat")
        self.star_btn.connect("clicked", lambda _b: self._on_toggle_pin())

        # In GTK HeaderBar pack_end, the first widget packed is placed at the far right.
        self.main_header_bar.pack_end(self.more_btn)
        self.main_header_bar.pack_end(self.info_btn)
        self.main_header_bar.pack_end(self.format_btn)
        self.main_header_bar.pack_end(self.star_btn)

        self.header_stack.add_named(self.main_header_bar, "main")

        self.category_header_bar = CategoryHeaderBar()
        self.category_header_bar.connect("category-changed", self._on_category_changed)
        self.category_header_bar.connect("abort", self._on_abort_category_change)
        self.header_stack.add_named(self.category_header_bar, "category")

        self.append(self.header_stack)

        # Overlay: WebView + bottom revealer
        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)

        self.webview = WebKit.WebView()
        self.webview.set_hexpand(True)
        self.webview.set_vexpand(True)
        self.webview.set_focusable(True)

        bg_rgba = Gdk.RGBA()
        bg_rgba.parse("#24252A" if self.is_dark_mode else "#FFFFFF")
        self.webview.set_background_color(bg_rgba)

        settings = self.webview.get_settings()
        try:
            settings.set_enable_javascript(True)
            settings.set_enable_developer_extras(True)
            if hasattr(settings, "set_enable_write_console_messages_to_stdout"):
                settings.set_enable_write_console_messages_to_stdout(True)
        except Exception:
            pass

        self._setup_message_handlers()

        self.webview.connect("load-changed", self._on_webview_load_changed)

        font_size = self.config_manager.get_font_size()
        initial_html = get_editor_html_page("", self.is_dark_mode, font_size)
        assets_uri = f"file://{get_assets_path()}/"
        self.webview.load_html(initial_html, assets_uri)

        overlay.set_child(self.webview)

        # Bottom formatting bar in revealer
        self.fmt_bar = FormattingBar(
            exec_fn=self._exec_js_format,
            insert_table_fn=self._insert_table_at_cursor,
            pick_image_fn=self._trigger_pick_image,
            toggle_pin_fn=self._on_toolbar_pin_toggled,
            is_pinned=self._is_toolbar_pinned
        )

        self.fmt_revealer = Gtk.Revealer()
        self.fmt_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.fmt_revealer.set_transition_duration(250)
        self.fmt_revealer.set_valign(Gtk.Align.END)
        self.fmt_revealer.set_halign(Gtk.Align.FILL)
        self.fmt_revealer.set_hexpand(True)
        self.fmt_revealer.set_reveal_child(True)
        self.fmt_revealer.set_child(self.fmt_bar)
        self.fmt_revealer.connect("notify::reveal-child", lambda _r, _p: self._sync_format_btn())

        # Mouse motion on bottom revealer so it stays visible while hovering
        revealer_motion = Gtk.EventControllerMotion()
        revealer_motion.connect("enter", self._on_toolbar_enter)
        revealer_motion.connect("motion", self._on_toolbar_motion)
        revealer_motion.connect("leave", self._on_toolbar_leave)
        self.fmt_revealer.add_controller(revealer_motion)

        overlay.add_overlay(self.fmt_revealer)

        # Mouse motion for auto-hide when moving near bottom edge of webview
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_webview_motion)
        motion.connect("leave", self._on_webview_leave)
        self.webview.add_controller(motion)

        self.append(overlay)

    # ── Toolbar auto-hide / hover / pin handling ──────────────────────────

    def _sync_format_btn(self):
        if hasattr(self, "format_btn") and hasattr(self, "fmt_revealer"):
            is_revealed = self.fmt_revealer.get_reveal_child()
            if self.format_btn.get_active() != is_revealed:
                self._syncing_format_btn = True
                self.format_btn.set_active(is_revealed)
                self._syncing_format_btn = False

    def _on_format_btn_toggled(self, btn):
        if getattr(self, "_syncing_format_btn", False):
            return
        reveal = btn.get_active()
        if reveal:
            self._show_toolbar()
        else:
            if self._toolbar_reveal_timeout:
                GLib.source_remove(self._toolbar_reveal_timeout)
                self._toolbar_reveal_timeout = None
            self.fmt_revealer.set_reveal_child(False)

    def _insert_table_at_cursor(self, rows: int, cols: int, has_header: bool):
        script = f"if (window.insertCustomTable) {{ window.insertCustomTable({rows}, {cols}, {'true' if has_header else 'false'}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _trigger_pick_image(self):
        self._on_js_pick_image(None, None)

    def _on_toolbar_pin_toggled(self, is_pinned: bool):
        self._is_toolbar_pinned = is_pinned
        self.db.set_setting("toolbar_pinned", "true" if is_pinned else "false")
        if is_pinned:
            self._show_toolbar()
        else:
            self._schedule_hide_toolbar()

    def _on_toolbar_enter(self, _ctrl, _x, _y):
        self._mouse_over_toolbar = True
        self._show_toolbar()

    def _on_toolbar_motion(self, _ctrl, _x, _y):
        self._mouse_over_toolbar = True
        self._show_toolbar()

    def _on_toolbar_leave(self, _ctrl):
        self._mouse_over_toolbar = False
        if not self._is_toolbar_pinned and not self._mouse_near_bottom:
            self._schedule_hide_toolbar()

    def _on_webview_motion(self, _ctrl, _x, y):
        if self._is_toolbar_pinned:
            return
        h = self.webview.get_height()
        if h > 0 and y >= h - 120:
            self._mouse_near_bottom = True
            self._show_toolbar()
        else:
            self._mouse_near_bottom = False
            if not self._mouse_over_toolbar:
                self._schedule_hide_toolbar()

    def _on_webview_leave(self, _ctrl):
        if self._is_toolbar_pinned:
            return
        self._mouse_near_bottom = False
        if not self._mouse_over_toolbar:
            self._schedule_hide_toolbar()

    def _show_toolbar(self):
        if self._toolbar_reveal_timeout:
            GLib.source_remove(self._toolbar_reveal_timeout)
            self._toolbar_reveal_timeout = None
        if not self.fmt_revealer.get_reveal_child():
            self.fmt_revealer.set_reveal_child(True)

    def _schedule_hide_toolbar(self):
        if self._is_toolbar_pinned:
            return
        if self._mouse_over_toolbar or self._mouse_near_bottom:
            return
        if hasattr(self, "fmt_bar") and self.fmt_bar.is_popover_open():
            return
        if self._toolbar_reveal_timeout:
            return

        def do_hide():
            if self._is_toolbar_pinned:
                self._toolbar_reveal_timeout = None
                return False
            if self._mouse_over_toolbar or self._mouse_near_bottom:
                self._toolbar_reveal_timeout = None
                return False
            if hasattr(self, "fmt_bar") and self.fmt_bar.is_popover_open():
                self._toolbar_reveal_timeout = None
                return False
            self.fmt_revealer.set_reveal_child(False)
            self._toolbar_reveal_timeout = None
            return False

        self._toolbar_reveal_timeout = GLib.timeout_add(1500, do_hide)

    def _on_webview_load_changed(self, _wv, event):
        if event == WebKit.LoadEvent.FINISHED:
            self._page_loaded = True
            font_size = self.config_manager.get_font_size()
            self.update_font_size(font_size)
            if self._pending_load_note:
                note = self._pending_load_note
                self._pending_load_note = None
                self.load_note(note)
            else:
                self.webview.evaluate_javascript("if (window.selectUntitledTitle) { window.selectUntitledTitle(); }", -1, None, None, None, None)
            GLib.idle_add(self.focus_editor)

    # ── WebKit message handlers ───────────────────────────────────────────

    def _setup_message_handlers(self):
        ucm = self.webview.get_user_content_manager()
        try:
            ucm.register_script_message_handler("contentChanged")
            ucm.connect("script-message-received::contentChanged", self._on_js_content_changed)
            ucm.register_script_message_handler("statsChanged")
            ucm.connect("script-message-received::statsChanged", self._on_js_stats_changed)
            ucm.register_script_message_handler("pickImage")
            ucm.connect("script-message-received::pickImage", self._on_js_pick_image)
            ucm.register_script_message_handler("uploadImage")
            ucm.connect("script-message-received::uploadImage", self._on_js_upload_image)
        except Exception as e:
            print("Message handler registration error:", e)

    # ── Stats popover ─────────────────────────────────────────────────────

    def _create_stats_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.connect("notify::visible", self._on_stats_popover_visible)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        title = Gtk.Label(label="Note Statistics")
        title.add_css_class("stilo-stats-title")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(24)

        self.stat_val_labels = {}
        for r, (txt, key) in enumerate([
            ("Words:", "words_val"), ("Characters:", "chars_val"),
            ("Paragraphs:", "paras_val"), ("Reading Time:", "read_val"),
            ("Created:", "created_val"), ("Modified:", "modified_val"),
        ]):
            lbl = Gtk.Label(label=txt)
            lbl.add_css_class("stilo-stats-label")
            lbl.set_halign(Gtk.Align.START)
            grid.attach(lbl, 0, r, 1, 1)

            val_lbl = Gtk.Label(label="—")
            val_lbl.add_css_class("stilo-stats-value")
            val_lbl.set_halign(Gtk.Align.END)
            grid.attach(val_lbl, 1, r, 1, 1)
            self.stat_val_labels[key] = val_lbl

        box.append(grid)
        popover.set_child(box)
        return popover

    def _on_stats_popover_visible(self, popover, _pspec):
        if popover.get_visible():
            self.update_stats_popover()
            if self._page_loaded:
                script = "if (window.getStats && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.statsChanged) { window.webkit.messageHandlers.statsChanged.postMessage(JSON.stringify(window.getStats())); }"
                self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def update_stats_popover(self):
        if not self.current_note:
            return
        self.stat_val_labels["words_val"].set_text(str(self.latest_stats.get("words", 0)))
        self.stat_val_labels["chars_val"].set_text(str(self.latest_stats.get("chars", 0)))
        self.stat_val_labels["paras_val"].set_text(str(self.latest_stats.get("paragraphs", 0)))
        self.stat_val_labels["read_val"].set_text(str(self.latest_stats.get("readTime", "1 min")))
        self.stat_val_labels["created_val"].set_text(format_relative_date(self.current_note.created_at))
        self.stat_val_labels["modified_val"].set_text(format_relative_date(self.current_note.updated_at))

    # ── Editor menu ───────────────────────────────────────────────────────

    def _create_more_menu(self) -> Gio.Menu:
        menu = Gio.Menu()

        s_theme = Gio.Menu()
        item_theme = Gio.MenuItem.new(None, None)
        item_theme.set_attribute_value("custom", GLib.Variant.new_string("theme"))
        s_theme.append_item(item_theme)
        menu.append_section(None, s_theme)

        s_font = Gio.Menu()
        item_font = Gio.MenuItem.new(None, None)
        item_font.set_attribute_value("custom", GLib.Variant.new_string("fontsize"))
        s_font.append_item(item_font)
        menu.append_section(None, s_font)

        s1 = Gio.Menu()
        s1.append("Note Statistics",    "editor.show-stats")
        menu.append_section(None, s1)

        s2 = Gio.Menu()
        s2.append("Edit Title…",        "editor.rename-title")
        s2.append("Change Category…",   "editor.edit-category")
        s2.append("Pin to Favorites",   "editor.toggle-pin")
        s2.append("Duplicate Note",     "editor.duplicate")
        menu.append_section(None, s2)

        s3 = Gio.Menu()
        s3.append("Export as Markdown…",    "editor.export-md")
        s3.append("Export as HTML…",        "editor.export-html")
        s3.append("Export as Plain Text…",  "editor.export-txt")
        menu.append_section(None, s3)

        s4 = Gio.Menu()
        s4.append("Delete Note", "editor.delete")
        menu.append_section(None, s4)

        return menu

    # ── Actions ───────────────────────────────────────────────────────────

    def setup_actions(self, window: Gtk.Window):
        ag = Gio.SimpleActionGroup()

        def act(name, cb):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p: cb())
            ag.add_action(a)

        act("undo", lambda: self._exec_js_format("undo"))
        act("redo", lambda: self._exec_js_format("redo"))
        act("increase-font-size", lambda: self.font_size_selector.increase())
        act("decrease-font-size", lambda: self.font_size_selector.decrease())
        act("reset-font-size",    lambda: self.font_size_selector.reset())
        act("rename-title",  lambda: self._on_title_clicked(None))
        act("edit-category", self.enter_edit_category)
        act("toggle-pin",    self._on_toggle_pin)
        act("duplicate",     self._on_duplicate)
        act("toggle-theme",  lambda: self.emit("toggle-app-theme"))
        act("show-stats",    lambda: self.info_btn.popup())
        act("export-md",     lambda: self._export_note("md",   window))
        act("export-html",   lambda: self._export_note("html", window))
        act("export-txt",    lambda: self._export_note("txt",  window))
        act("toggle-format-toolbar", lambda: self.format_btn.set_active(not self.format_btn.get_active()))
        act("delete",        self._on_delete)

        self.insert_action_group("editor", ag)

        app = window.get_application()
        if app:
            app.set_accels_for_action("editor.undo", ["<Control>z"])
            app.set_accels_for_action("editor.redo", ["<Control>y", "<Control><Shift>z"])
            app.set_accels_for_action("editor.increase-font-size", ["<Control>plus", "<Control>equal"])
            app.set_accels_for_action("editor.decrease-font-size", ["<Control>minus", "<Control>underscore"])
            app.set_accels_for_action("editor.reset-font-size", ["<Control>0"])
            app.set_accels_for_action("editor.toggle-format-toolbar", ["<Control><Shift>f"])

    # ── Category editing ──────────────────────────────────────────────────

    def enter_edit_category(self):
        if not self.current_note:
            return
        categories = [c.name for c in self.db.get_categories()]
        self.category_header_bar.set_categories(categories)
        self.header_stack.set_visible_child_name("category")
        self.category_header_bar.activate(self.current_note.category or "")

    def _on_category_changed(self, _bar, new_category: str):
        if not self.current_note:
            return
        clean_cat = new_category.strip()
        self.current_note.category = clean_cat
        if clean_cat:
            self.db.create_category(clean_cat)
        self.db.save_note(note_id=self.current_note.id, category=clean_cat)
        self.header_stack.set_visible_child_name("main")
        self.emit("note-category-changed", self.current_note.id, clean_cat)

    def _on_abort_category_change(self, _bar):
        self.header_stack.set_visible_child_name("main")

    # ── Note loading & theme ──────────────────────────────────────────────

    def load_note(self, note: Note):
        self.flush_save()
        full_note = self.db.get_note(note.id)
        if full_note:
            note = full_note
        self.current_note = note
        self.header_stack.set_visible_child_name("main")
        self.title_label.set_text(note.title)
        self.status_label.set_text("Saved")

        # Update star button state
        self._update_star_btn(note.is_pinned)

        # Pre-compute statistics immediately so Note Statistics popover has accurate values
        self.latest_stats = compute_note_stats(note.content_html, note.content_markdown)
        self.update_stats_popover()

        if not self._page_loaded:
            self._pending_load_note = note
            return

        html_content = note.content_html
        if not html_content and note.content_markdown:
            html_content = markdown_to_html(note.content_markdown)
        if not html_content:
            html_content = f"<h1>{note.title}</h1><div><br></div>"

        escaped_html = json.dumps(html_content)
        is_untitled = bool(note.title == "Untitled Note" or not note.title.strip())
        script = f"if (window.setEditorContent) {{ window.setEditorContent({escaped_html}, {'true' if is_untitled else 'false'}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

        self._show_toolbar()
        self.update_stats_popover()
        GLib.idle_add(self.focus_editor)

    def update_theme(self, is_dark: bool):
        self.is_dark_mode = is_dark
        bg_rgba = Gdk.RGBA()
        bg_rgba.parse("#24252A" if is_dark else "#FFFFFF")
        self.webview.set_background_color(bg_rgba)
        script = f"if (window.setEditorTheme) {{ window.setEditorTheme({'true' if is_dark else 'false'}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)
        if hasattr(self, "theme_selector"):
            self.theme_selector.populate()

    def update_font_size(self, size: int):
        script = f"if (window.setFontSize) {{ window.setFontSize({size}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _on_toggle_theme(self, _btn):
        """Emit signal up to the window so it can do full Adw theme toggle."""
        self.emit("toggle-app-theme")

    def _update_star_btn(self, is_pinned: bool):
        if is_pinned:
            self.star_btn.set_icon_name("starred-symbolic")
            self.star_btn.set_tooltip_text("Remove from Favorites")
            self.star_btn.add_css_class("stilo-star-active")
        else:
            self.star_btn.set_icon_name("non-starred-symbolic")
            self.star_btn.set_tooltip_text("Pin to Favorites")
            self.star_btn.remove_css_class("stilo-star-active")

    # ── JS / WebKit callbacks ─────────────────────────────────────────────

    def _exec_js_format(self, command: str):
        script = f"window.execFormatting({json.dumps(command)});"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _on_js_content_changed(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            json_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if not json_str:
                return
            data = json.loads(json_str)
            if not self.current_note:
                return

            new_title   = data.get("title",   self.current_note.title)
            new_excerpt = data.get("excerpt",  self.current_note.excerpt)
            new_html    = data.get("html",     self.current_note.content_html)
            stats       = data.get("stats",    {})
            has_todo    = data.get("has_todo", False)

            self.latest_stats = stats
            self.title_label.set_text(new_title)

            self.current_note.title = new_title
            self.current_note.excerpt = new_excerpt
            self.current_note.content_html = new_html
            self.current_note.has_todo = has_todo

            self.update_stats_popover()

            self._pending_save_data = {
                "note_id": self.current_note.id,
                "title": new_title,
                "excerpt": new_excerpt,
                "html": new_html,
                "has_todo": has_todo,
            }
            self.status_label.set_text("Saving…")
            self._schedule_save()
        except Exception as e:
            print("Error parsing content change:", e)

    def _on_js_stats_changed(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            json_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if not json_str:
                return
            stats = json.loads(json_str)
            if isinstance(stats, dict):
                self.latest_stats = stats
                self.update_stats_popover()
        except Exception as e:
            print("Stats changed error:", e)

    def _schedule_save(self):
        if self._save_timeout_id:
            GLib.source_remove(self._save_timeout_id)
            self._save_timeout_id = None

        def do_save():
            self._save_timeout_id = None
            if not self._pending_save_data:
                return False
            data = dict(self._pending_save_data)

            def worker():
                try:
                    md_content = html_to_markdown(data["html"])
                    self.db.save_note(
                        note_id=data["note_id"],
                        title=data["title"],
                        excerpt=data["excerpt"],
                        content_html=data["html"],
                        content_markdown=md_content,
                        has_todo=data["has_todo"]
                    )
                    if self.current_note and self.current_note.id == data["note_id"]:
                        self.current_note.content_markdown = md_content

                    def on_done():
                        if self._pending_save_data and self._pending_save_data.get("html") == data["html"]:
                            self._pending_save_data = None
                            self.status_label.set_text("Saved")
                            self.emit("note-updated", data["note_id"], data["title"], data["excerpt"], data["html"], md_content, [], data["has_todo"])
                        return False

                    GLib.idle_add(on_done)
                except Exception as e:
                    print("Background save error:", e)

            threading.Thread(target=worker, daemon=True).start()
            return False

        self._save_timeout_id = GLib.timeout_add(250, do_save)

    def flush_save(self):
        """Synchronously commit any pending changes immediately."""
        if self._save_timeout_id:
            GLib.source_remove(self._save_timeout_id)
            self._save_timeout_id = None

        if self._pending_save_data:
            data = self._pending_save_data
            self._pending_save_data = None
            try:
                md = html_to_markdown(data["html"])
                self.db.save_note(
                    note_id=data["note_id"],
                    title=data["title"],
                    excerpt=data["excerpt"],
                    content_html=data["html"],
                    content_markdown=md,
                    has_todo=data["has_todo"]
                )
                if self.current_note and self.current_note.id == data["note_id"]:
                    self.current_note.content_markdown = md
                self.status_label.set_text("Saved")
                self.emit("note-updated", data["note_id"], data["title"], data["excerpt"], data["html"], md, [], data["has_todo"])
            except Exception as e:
                print("Flush save error:", e)

    def _on_js_upload_image(self, _ucm, js_result):
        """Handle pasted or dropped images sent from JavaScript as binary attachments."""
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            json_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if not json_str:
                return
            data = json.loads(json_str)
            filename = data.get("filename", "image.png")
            mime_type = data.get("mimeType", "image/png")
            data_url = data.get("dataUrl", "")
            if not data_url or "," not in data_url or not self.current_note:
                return

            base64_payload = data_url.split(",", 1)[1]
            binary_data = base64.b64decode(base64_payload)

            att_id = self.db.save_attachment(
                note_id=self.current_note.id,
                filename=filename,
                mime_type=mime_type,
                data=binary_data
            )
            uri = f"attachment://{att_id}"
            script = f"insertImageAtCursor({json.dumps(uri)}, {json.dumps(filename)});"
            self.webview.evaluate_javascript(script, -1, None, None, None, None)
        except Exception as e:
            print("Error handling uploaded image:", e)

    def _on_js_pick_image(self, _ucm, _js_result):
        if not self.current_note:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Image")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_pixbuf_formats()
        filters.append(img_filter)
        dialog.set_filters(filters)

        def on_open_finish(d, res):
            try:
                f = d.open_finish(res)
                if f and self.current_note:
                    file_path = f.get_path()
                    if file_path:
                        p = Path(file_path)
                        binary_data = p.read_bytes()
                        filename = p.name
                        mime_type = mimetypes.guess_type(file_path)[0] or "image/png"
                        att_id = self.db.save_attachment(
                            note_id=self.current_note.id,
                            filename=filename,
                            mime_type=mime_type,
                            data=binary_data
                        )
                        uri = f"attachment://{att_id}"
                        script = f"insertImageAtCursor({json.dumps(uri)}, {json.dumps(filename)});"
                        self.webview.evaluate_javascript(script, -1, None, None, None, None)
            except Exception as e:
                print("Error opening image file:", e)

        dialog.open(self.get_root(), None, on_open_finish)

    # ── Title rename ──────────────────────────────────────────────────────

    def _on_title_clicked(self, _btn):
        if not self.current_note:
            return
        dialog = Adw.AlertDialog.new("Rename Note", "Enter a new title for this note:")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_text(self.current_note.title)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        def on_response(_d, response):
            if response == "rename":
                new_title = entry.get_text().strip()
                if new_title:
                    self.title_label.set_text(new_title)
                    script = f"""
                    var h1 = document.querySelector('h1');
                    if (h1) {{ h1.innerText = {json.dumps(new_title)}; }}
                    else {{ document.execCommand('insertHTML', false, '<h1>' + {json.dumps(new_title)} + '</h1>'); }}
                    notifyChange();
                    """
                    self.webview.evaluate_javascript(script, -1, None, None, None, None)

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    # ── Note actions ──────────────────────────────────────────────────────

    def _on_toggle_pin(self):
        if self.current_note:
            self.current_note.is_pinned = not self.current_note.is_pinned
            self._update_star_btn(self.current_note.is_pinned)
            self.emit("note-pin-toggled", self.current_note.id)

    def _on_duplicate(self):
        if self.current_note:
            self.emit("note-duplicated", self.current_note.id)

    def _on_delete(self):
        if self.current_note:
            self.emit("note-deleted", self.current_note.id)

    def _export_note(self, fmt: str, window: Gtk.Window):
        if self.current_note:
            export_note_dialog(window, self.current_note, fmt)

    def grab_focus(self) -> bool:
        if hasattr(self, "webview") and self.webview:
            return self.webview.grab_focus()
        return super().grab_focus()

    def focus_editor(self):
        if hasattr(self, "webview") and self.webview:
            self.webview.grab_focus()
            script = "if (window.focusEditor) { window.focusEditor(); }"
            self.webview.evaluate_javascript(script, -1, None, None, None, None)
        return False

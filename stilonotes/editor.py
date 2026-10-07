# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import base64
import mimetypes
import threading
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')
from gi.repository import Adw, Gtk, WebKit, Gio, GLib, GObject, Gdk, Pango

from stilonotes.category_header_bar import CategoryHeaderBar
from stilonotes.config_manager import ConfigManager
from stilonotes.theme_selector import ThemeSelector
from stilonotes.font_size_selector import FontSizeSelector
from stilonotes.models import Note
from stilonotes.editor_html import get_editor_html_page
from stilonotes.markdown_utils import compute_note_stats, format_relative_date, html_to_markdown, markdown_to_html, is_untitled_title
from stilonotes.exporter import export_note_dialog, Printer
from stilonotes.page_setup import show_page_setup_dialog, create_default_page_setup
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

    def __init__(self, exec_fn, insert_table_fn=None, pick_image_fn=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._exec = exec_fn
        self._insert_table = insert_table_fn
        self._pick_image = pick_image_fn
        self.h_pop = None
        self.table_pop = None
        self._build()

    def is_popover_open(self) -> bool:
        h_open = bool(self.h_pop and self.h_pop.get_visible())
        t_open = bool(self.table_pop and self.table_pop.get_visible())
        return h_open or t_open

    def _build(self):
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(sep)

        bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar_box.add_css_class("formatting-bar")
        self.append(bar_box)

        # Flowbox for toolbar buttons so that narrowing the window wraps nicely
        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.CENTER)
        flowbox.set_halign(Gtk.Align.CENTER)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.set_activate_on_single_click(False)
        flowbox.set_can_focus(False)
        flowbox.set_max_children_per_line(30)
        flowbox.set_min_children_per_line(1)
        flowbox.set_row_spacing(4)
        flowbox.set_column_spacing(2)
        flowbox.set_hexpand(True)
        flowbox.add_css_class("formatting-flowbox")
        bar_box.append(flowbox)

        def _setup_flow_child(w):
            child = w.get_parent()
            if isinstance(child, Gtk.FlowBoxChild):
                child.set_can_focus(False)
                child.set_focusable(False)

        # 0. Undo & Redo
        self._add_btn(flowbox, "edit-undo-symbolic", "Undo (Ctrl+Z)", "undo")
        self._add_btn(flowbox, "edit-redo-symbolic", "Redo (Ctrl+Y)", "redo")

        # 1. Heading menu button
        heading_menu = Gtk.MenuButton()
        heading_menu.set_icon_name("heading-symbolic")
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
        flowbox.append(heading_menu)
        _setup_flow_child(heading_menu)

        # 2. Text styling
        for icon, tip, cmd in [
            ("format-text-bold-symbolic",          "Bold",             "bold"),
            ("format-text-italic-symbolic",        "Italic",           "italic"),
            ("format-text-strikethrough-symbolic", "Strikethrough",    "strike"),
            ("format-text-underline-symbolic",     "Underline",        "underline"),
            ("marker-symbolic",                    "Highlight",        "highlight"),
            ("code-symbolic",                      "Inline Code",      "inline-code"),
            ("eraser-symbolic",                    "Clear Formatting", "clear-format"),
        ]:
            self._add_btn(flowbox, icon, tip, cmd)

        # 3. Lists
        for icon, tip, cmd in [
            ("view-list-bullet-symbolic",  "Bullet List",   "bullet"),
            ("view-list-ordered-symbolic", "Numbered List", "number"),
            ("checkbox-checked-symbolic",  "Checklist",     "todo"),
        ]:
            self._add_btn(flowbox, icon, tip, cmd)

        # 4. Blocks & Markdown Elements
        for icon, tip, cmd in [
            ("quotation-symbolic",       "Blockquote",             "quote"),
            ("code-block-symbolic",      "Code Block",             "code"),
            ("insert-link-symbolic",     "Insert Link (Ctrl+K)",   "link"),
            ("view-continuous-symbolic", "Horizontal Rule",        "divider"),
        ]:
            self._add_btn(flowbox, icon, tip, cmd)

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
        flowbox.append(table_menu)
        _setup_flow_child(table_menu)

        # 6. Insert Image button
        img_btn = Gtk.Button()
        img_btn.set_icon_name("insert-image-symbolic")
        img_btn.set_tooltip_text("Insert Image")
        img_btn.set_focus_on_click(False)
        img_btn.add_css_class("flat")
        img_btn.connect("clicked", lambda _b: self._on_image_clicked())
        flowbox.append(img_btn)
        _setup_flow_child(img_btn)

    def _on_image_clicked(self):
        if self._pick_image:
            self._pick_image()
        else:
            self._exec("image")

    def _add_btn(self, box, icon_name, tooltip, cmd):
        btn = Gtk.Button()
        btn.set_icon_name(icon_name)
        btn.set_tooltip_text(tooltip)
        btn.set_focus_on_click(False)
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _b, c=cmd: self._exec(c))
        box.append(btn)
        child = btn.get_parent()
        if isinstance(child, Gtk.FlowBoxChild):
            child.set_can_focus(False)
            child.set_focusable(False)
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
        "tag-clicked":           (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "open-note-link":        (GObject.SignalFlags.RUN_FIRST, None, (str, str,)),
        "back":                  (GObject.SignalFlags.RUN_FIRST, None, ()),
        "toggle-sidebar":        (GObject.SignalFlags.RUN_FIRST, None, ()),
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
        self._is_toolbar_pinned = self.config_manager.get_toolbar_pinned()
        self._page_loaded = False
        self._pending_load_note = None
        self._save_timeout_id = None
        self._current_printer = None
        self.is_read_only = False
        self.page_setup = self.config_manager.get_page_setup() if hasattr(self.config_manager, "get_page_setup") else create_default_page_setup()
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
        self.back_btn.set_tooltip_text("Back to Notes (Esc)")
        self.back_btn.connect("clicked", lambda _b: self.emit("back"))
        self.main_header_bar.pack_start(self.back_btn)

        self.edit_btn = Gtk.ToggleButton()
        self.edit_btn.set_icon_name("edit-symbolic")
        self.edit_btn.set_tooltip_text("Edit Note (Ctrl+E)")
        self.edit_btn.set_focus_on_click(False)
        self.edit_btn.add_css_class("flat")
        self.edit_btn.connect("toggled", self._on_edit_btn_toggled)
        self.main_header_bar.pack_start(self.edit_btn)

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

        # 3. Print button
        self.print_btn = Gtk.Button()
        self.print_btn.set_icon_name("printer-symbolic")
        self.print_btn.set_tooltip_text("Print Note (Ctrl+P)")
        self.print_btn.add_css_class("flat")
        self.print_btn.set_action_name("editor.print")

        # 4. Format Toolbar Toggle button (controls toolbar pinning)
        self.format_btn = Gtk.ToggleButton()
        self.format_btn.set_icon_name("format-text-bold-symbolic")
        self.format_btn.set_tooltip_text("Toggle Formatting Bar (Ctrl+Shift+F)")
        self.format_btn.set_focus_on_click(False)
        self.format_btn.add_css_class("flat")
        self.format_btn.set_active(self._is_toolbar_pinned)
        self.format_btn.connect("toggled", self._on_format_btn_toggled)

        # 5. Star / Favorites toggle button
        self.star_btn = Gtk.Button()
        self.star_btn.set_icon_name("non-starred-symbolic")
        self.star_btn.set_tooltip_text("Pin to Favorites")
        self.star_btn.add_css_class("flat")
        self.star_btn.connect("clicked", lambda _b: self._on_toggle_pin())

        # 6. Lock / Private toggle indicator button
        self.lock_btn = Gtk.Button()
        self.lock_btn.set_icon_name("channel-secure-symbolic")
        self.lock_btn.set_tooltip_text("Lock Private Notes")
        self.lock_btn.add_css_class("flat")
        self.lock_btn.connect("clicked", lambda _b: self._on_lock_clicked())
        self.lock_btn.set_visible(False)

        # In GTK HeaderBar pack_end, the first widget packed is placed at the far right.
        self.main_header_bar.pack_end(self.more_btn)
        self.main_header_bar.pack_end(self.info_btn)
        self.main_header_bar.pack_end(self.print_btn)
        self.main_header_bar.pack_end(self.format_btn)
        self.main_header_bar.pack_end(self.star_btn)
        self.main_header_bar.pack_end(self.lock_btn)

        self.header_stack.add_named(self.main_header_bar, "main")

        self.category_header_bar = CategoryHeaderBar()
        self.category_header_bar.connect("category-changed", self._on_category_changed)
        self.category_header_bar.connect("abort", self._on_abort_category_change)
        self.header_stack.add_named(self.category_header_bar, "category")

        self.append(self.header_stack)

        # Conflict Banner for external edits
        self.conflict_banner = Adw.Banner.new("This note was modified in another window.")
        self.conflict_banner.set_button_label("Reload")
        self.conflict_banner.set_revealed(False)
        self.conflict_banner.connect("button-clicked", self._on_conflict_reload_clicked)
        self.append(self.conflict_banner)

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
        self.webview.connect("decide-policy", self._on_decide_policy)

        font_size = self.config_manager.get_font_size()
        heading_scale = self.config_manager.get_heading_scale()
        code_font_size = self.config_manager.get_code_font_size()
        quote_font_size = self.config_manager.get_quote_font_size()
        font_family = self.config_manager.get_font_family()
        initial_html = get_editor_html_page(
            "", self.is_dark_mode, font_size, heading_scale, code_font_size, quote_font_size,
            font_family=font_family
        )
        assets_uri = f"file://{get_assets_path()}/"
        self.webview.load_html(initial_html, assets_uri)

        overlay.set_child(self.webview)

        # Bottom formatting bar in revealer
        self.fmt_bar = FormattingBar(
            exec_fn=self._exec_js_format,
            insert_table_fn=self._insert_table_at_cursor,
            pick_image_fn=self._trigger_pick_image,
        )

        self.fmt_revealer = Gtk.Revealer()
        self.fmt_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.fmt_revealer.set_transition_duration(250)
        self.fmt_revealer.set_valign(Gtk.Align.END)
        self.fmt_revealer.set_halign(Gtk.Align.FILL)
        self.fmt_revealer.set_hexpand(True)
        self.fmt_revealer.set_reveal_child(self._is_toolbar_pinned)
        self.fmt_revealer.set_child(self.fmt_bar)

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

    def set_read_only(self, read_only: bool):
        """Toggle between read-only mode and edit mode."""
        self.is_read_only = bool(read_only)

        if hasattr(self, "edit_btn") and self.edit_btn:
            try:
                self.edit_btn.handler_block_by_func(self._on_edit_btn_toggled)
                self.edit_btn.set_active(not self.is_read_only)
                self.edit_btn.handler_unblock_by_func(self._on_edit_btn_toggled)
            except Exception:
                self.edit_btn.set_active(not self.is_read_only)

            if self.is_read_only:
                self.edit_btn.set_tooltip_text("Edit Note (Ctrl+E)")
            else:
                self.edit_btn.set_tooltip_text("Lock for Reading (Ctrl+E)")

        if hasattr(self, "format_btn") and self.format_btn:
            self.format_btn.set_sensitive(not self.is_read_only)

        if self.is_read_only:
            if hasattr(self, "fmt_revealer") and self.fmt_revealer:
                self.fmt_revealer.set_reveal_child(False)
        else:
            if getattr(self, "_is_toolbar_pinned", False):
                self._show_toolbar()

        if hasattr(self, "webview") and self.webview:
            script = f"if (window.setReadOnly) {{ window.setReadOnly({'true' if self.is_read_only else 'false'}); }}"
            self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _on_edit_btn_toggled(self, btn):
        is_editing = btn.get_active()
        self.set_read_only(not is_editing)
        if is_editing:
            GLib.idle_add(self.focus_editor)

    def _on_format_btn_toggled(self, btn):
        pinned = btn.get_active()
        self._is_toolbar_pinned = pinned
        self.config_manager.set_toolbar_pinned(pinned)
        if pinned and not getattr(self, "is_read_only", False):
            self._show_toolbar()
        else:
            if self._toolbar_reveal_timeout:
                GLib.source_remove(self._toolbar_reveal_timeout)
                self._toolbar_reveal_timeout = None
            if not self._mouse_over_toolbar and not self._mouse_near_bottom:
                self.fmt_revealer.set_reveal_child(False)
            else:
                self._schedule_hide_toolbar()

    def _insert_table_at_cursor(self, rows: int, cols: int, has_header: bool):
        if getattr(self, "is_read_only", False):
            return
        script = f"if (window.insertCustomTable) {{ window.insertCustomTable({rows}, {cols}, {'true' if has_header else 'false'}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _trigger_pick_image(self):
        if getattr(self, "is_read_only", False):
            return
        self._on_js_pick_image(None, None)

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
        if getattr(self, "is_read_only", False):
            return
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
                if isinstance(self._pending_load_note, tuple):
                    note, is_new = self._pending_load_note
                else:
                    note, is_new = self._pending_load_note, False
                self._pending_load_note = None
                self.load_note(note, is_new=is_new)
            else:
                self.webview.evaluate_javascript("if (window.selectUntitledTitle) { window.selectUntitledTitle(); }", -1, None, None, None, None)
                GLib.idle_add(self.focus_editor)

    # ── WebKit message handlers ───────────────────────────────────────────

    def _setup_message_handlers(self):
        ucm = self.webview.get_user_content_manager()
        self._message_handler_ids = []
        try:
            ucm.register_script_message_handler("contentChanged")
            self._message_handler_ids.append(ucm.connect("script-message-received::contentChanged", self._on_js_content_changed))
            ucm.register_script_message_handler("statsChanged")
            self._message_handler_ids.append(ucm.connect("script-message-received::statsChanged", self._on_js_stats_changed))
            ucm.register_script_message_handler("pickImage")
            self._message_handler_ids.append(ucm.connect("script-message-received::pickImage", self._on_js_pick_image))
            ucm.register_script_message_handler("uploadImage")
            self._message_handler_ids.append(ucm.connect("script-message-received::uploadImage", self._on_js_upload_image))
            ucm.register_script_message_handler("tagClicked")
            self._message_handler_ids.append(ucm.connect("script-message-received::tagClicked", self._on_js_tag_clicked))
            ucm.register_script_message_handler("openNoteLink")
            self._message_handler_ids.append(ucm.connect("script-message-received::openNoteLink", self._on_js_open_note_link))
            ucm.register_script_message_handler("categorySelected")
            self._message_handler_ids.append(ucm.connect("script-message-received::categorySelected", self._on_js_category_selected))
            ucm.register_script_message_handler("printNote")
            self._message_handler_ids.append(ucm.connect("script-message-received::printNote", lambda _ucm, _msg: self._print_note(self.get_root())))
            ucm.register_script_message_handler("insertLink")
            self._message_handler_ids.append(ucm.connect("script-message-received::insertLink", self._on_js_insert_link))
            ucm.register_script_message_handler("openExternalUrl")
            self._message_handler_ids.append(ucm.connect("script-message-received::openExternalUrl", self._on_js_open_external_url))
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
        s1.append("Toggle Sidebar",     "editor.toggle-sidebar")
        s1.append("Note Statistics",    "editor.show-stats")
        menu.append_section(None, s1)

        s2 = Gio.Menu()
        s2.append("Change Category…",   "editor.edit-category")
        s2.append("Pin to Favorites",   "editor.toggle-pin")
        is_locked = bool(self.current_note and self.current_note.is_locked)
        s2.append("Remove from Private Notes" if is_locked else "Move to Private Notes", "editor.toggle-lock")
        s2.append("Duplicate Note",     "editor.duplicate")
        menu.append_section(None, s2)

        s3 = Gio.Menu()
        s3.append("Open…",                  "win.open-file")
        s3.append("Page Setup…",            "editor.page-setup")
        s3.append("Print…",                 "editor.print")
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
        act("highlight",    lambda: self._exec_js_format("highlight"))
        act("clear-format", lambda: self._exec_js_format("clear-format"))
        act("increase-font-size", lambda: self.font_size_selector.increase())
        act("decrease-font-size", lambda: self.font_size_selector.decrease())
        act("reset-font-size",    lambda: self.font_size_selector.reset())
        act("toggle-sidebar",     lambda: self.emit("toggle-sidebar"))
        act("rename-title",  lambda: self._on_title_clicked(None))
        act("edit-category", self.enter_edit_category)
        act("toggle-pin",    self._on_toggle_pin)
        act("toggle-lock",   self._on_toggle_lock)
        act("duplicate",     self._on_duplicate)
        act("toggle-theme",  lambda: self.emit("toggle-app-theme"))
        act("show-stats",    lambda: self.info_btn.popup())
        act("page-setup",    lambda: self._on_page_setup(window))
        act("print",         lambda: self._print_note(window))
        act("export-md",     lambda: self._export_note("md",   window))
        act("export-html",   lambda: self._export_note("html", window))
        act("export-txt",    lambda: self._export_note("txt",  window))
        act("toggle-edit",   lambda: self.set_read_only(not self.is_read_only))
        act("toggle-format-toolbar", lambda: self.format_btn.set_active(not self.format_btn.get_active()))
        act("insert-link",   lambda: self._exec_js_format("link"))
        act("delete",        self._on_delete)

        self.insert_action_group("editor", ag)
        self.print_btn.set_action_name("editor.print")

        shortcut_ctrl = Gtk.ShortcutController.new()
        shortcut_ctrl.set_scope(Gtk.ShortcutScope.LOCAL)
        shortcut_ctrl.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Control>e"),
                Gtk.NamedAction.new("editor.toggle-edit")
            )
        )
        shortcut_ctrl.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Control>p"),
                Gtk.NamedAction.new("editor.print")
            )
        )
        shortcut_ctrl.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Control><Shift>p"),
                Gtk.NamedAction.new("editor.page-setup")
            )
        )
        shortcut_ctrl.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Control>k"),
                Gtk.NamedAction.new("editor.insert-link")
            )
        )
        self.add_controller(shortcut_ctrl)

        app = window.get_application()
        if app:
            app.set_accels_for_action("editor.toggle-edit", ["<Control>e"])
            app.set_accels_for_action("editor.undo", ["<Control>z"])
            app.set_accels_for_action("editor.redo", ["<Control>y", "<Control><Shift>z"])
            app.set_accels_for_action("editor.highlight", ["<Control><Shift>h"])
            app.set_accels_for_action("editor.clear-format", ["<Control>backslash", "<Control>m"])
            app.set_accels_for_action("editor.increase-font-size", ["<Control>plus", "<Control>equal"])
            app.set_accels_for_action("editor.decrease-font-size", ["<Control>minus", "<Control>underscore"])
            app.set_accels_for_action("editor.reset-font-size", ["<Control>0"])
            app.set_accels_for_action("editor.toggle-sidebar", ["<Control>backslash", "F11"])
            app.set_accels_for_action("editor.toggle-format-toolbar", ["<Control><Shift>f"])
            app.set_accels_for_action("editor.page-setup", ["<Control><Shift>p"])
            app.set_accels_for_action("editor.print", ["<Control>p"])
            app.set_accels_for_action("editor.insert-link", ["<Control>k"])

    # ── Category editing ──────────────────────────────────────────────────

    def enter_edit_category(self):
        if not self.current_note:
            return
        categories = [c.name for c in self.db.get_categories()]
        self.category_header_bar.set_categories(categories)
        self.header_stack.set_visible_child_name("category")
        curr_cat = (self.current_note.category or "").strip()
        if curr_cat.lower() == "uncategorized":
            curr_cat = ""
        self.category_header_bar.activate(curr_cat)

    def _on_category_changed(self, _bar, new_category: str):
        if not self.current_note:
            return
        clean_cat = (new_category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""
        self.current_note.category = clean_cat
        if self._pending_save_data:
            self._pending_save_data["category"] = clean_cat
        if clean_cat:
            self.db.create_category(clean_cat)
        self.db.save_note(note_id=self.current_note.id, category=clean_cat, sender=self)
        self.header_stack.set_visible_child_name("main")
        self.emit("note-category-changed", self.current_note.id, clean_cat)

    def _on_abort_category_change(self, _bar):
        self.header_stack.set_visible_child_name("main")

    # ── External Sync & Conflict Handling ─────────────────────────────────

    def show_conflict_banner(self):
        self.conflict_banner.set_revealed(True)

    def hide_conflict_banner(self):
        self.conflict_banner.set_revealed(False)

    def has_pending_changes(self) -> bool:
        return self._pending_save_data is not None

    def _on_conflict_reload_clicked(self, _banner):
        self.hide_conflict_banner()
        if self._save_timeout_id:
            GLib.source_remove(self._save_timeout_id)
            self._save_timeout_id = None
        self._pending_save_data = None
        if self.current_note:
            full = self.db.get_note(self.current_note.id)
            if full:
                self.reload_note_from_db(full)

    def reload_note_from_db(self, note: Note):
        """Reload note content from DB without resetting scroll or focus unnecessarily."""
        self.hide_conflict_banner()
        self.current_note = note
        self.title_label.set_text(note.title)
        self.status_label.set_text("Saved")
        self._update_star_btn(note.is_pinned)
        self._update_lock_ui()
        self.latest_stats = compute_note_stats(note.content_html, note.content_markdown)
        self.update_stats_popover()

        html_content = note.content_html
        if not html_content and note.content_markdown:
            html_content = markdown_to_html(note.content_markdown)
        if not html_content:
            html_content = f"<h1>{note.title}</h1><div><br></div>"

        escaped_html = json.dumps(html_content)
        read_only_js = "true" if getattr(self, "is_read_only", False) else "false"
        script = f"if (window.setEditorContent) {{ window.setEditorContent({escaped_html}, false, {read_only_js}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)
        self._sync_autocomplete_data()

    # ── Note loading & theme ──────────────────────────────────────────────

    def load_note(self, note: Note, is_new: Optional[bool] = None):
        self.hide_conflict_banner()
        self.flush_save()
        full_note = self.db.get_note(note.id)
        if full_note:
            note = full_note
        self.current_note = note
        self.header_stack.set_visible_child_name("main")
        self.title_label.set_text(note.title)
        self.status_label.set_text("Saved")

        if is_new is None:
            has_body = bool((note.content_markdown or "").strip() or (note.content_html or "").strip())
            is_new = not has_body and is_untitled_title(note.title)

        self.set_read_only(not is_new)

        # Update star button state
        self._update_star_btn(note.is_pinned)
        self._update_lock_ui()

        # Pre-compute statistics immediately so Note Statistics popover has accurate values
        self.latest_stats = compute_note_stats(note.content_html, note.content_markdown)
        self.update_stats_popover()

        if not self._page_loaded:
            self._pending_load_note = (note, is_new)
            return

        html_content = note.content_html
        if not html_content and note.content_markdown:
            html_content = markdown_to_html(note.content_markdown)
        if not html_content:
            html_content = f"<h1>{note.title}</h1><div><br></div>"

        escaped_html = json.dumps(html_content)
        is_untitled = is_untitled_title(note.title)
        read_only_js = "true" if self.is_read_only else "false"
        script = f"if (window.setEditorContent) {{ window.setEditorContent({escaped_html}, {'true' if is_untitled else 'false'}, {read_only_js}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

        if not self.is_read_only:
            self._show_toolbar()
            GLib.idle_add(self.focus_editor)
        else:
            if hasattr(self, "fmt_revealer") and self.fmt_revealer:
                self.fmt_revealer.set_reveal_child(False)

        self.update_stats_popover()
        self._sync_autocomplete_data()

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
        self.update_typography()

    def update_typography(self):
        scale = self.config_manager.get_editor_zoom_level()
        if hasattr(self.webview, "set_zoom_level"):
            self.webview.set_zoom_level(scale)

        base_font_pt = round(16 * scale)
        code_font_px = round(14 * scale)
        quote_font_pt = round(16 * scale)
        font_family_stack = self.config_manager.get_font_family_stack()
        config_json = json.dumps({
            "zoomLevel": scale,
            "fontSize": base_font_pt,
            "headingScale": 1.0,
            "codeFontSize": code_font_px,
            "quoteFontSize": quote_font_pt,
            "fontFamily": font_family_stack,
        })
        script = f"if (window.setTypography) {{ window.setTypography({config_json}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def update_font_family(self, family: str):
        self.config_manager.set_font_family(family)
        self.update_typography()

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
        if getattr(self, "is_read_only", False):
            return
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
            tags        = data.get("tags",     [])
            stats       = data.get("stats",    {})
            has_todo    = data.get("has_todo", False)

            self.latest_stats = stats
            self.title_label.set_text(new_title)

            self.current_note.title = new_title
            self.current_note.excerpt = new_excerpt
            self.current_note.content_html = new_html
            self.current_note.tags = tags
            self.current_note.has_todo = has_todo

            self.update_stats_popover()

            curr_cat = (self.current_note.category or "").strip()
            if curr_cat.lower() == "uncategorized":
                curr_cat = ""
            self._pending_save_data = {
                "note_id": self.current_note.id,
                "title": new_title,
                "excerpt": new_excerpt,
                "html": new_html,
                "tags": tags,
                "has_todo": has_todo,
                "category": curr_cat,
            }
            self.status_label.set_text("Saving…")
            self._schedule_save()
        except Exception as e:
            print("Error parsing content change:", e)

    def _sync_autocomplete_data(self):
        """Send existing categories, tags, and note titles to editor WebKit for instant autocomplete."""
        try:
            categories = [c.name for c in self.db.get_categories()]
            tags = [t[0] for t in self.db.get_all_tags()]
            notes = self.db.get_all_note_titles()
            payload = json.dumps({
                "categories": categories,
                "tags": tags,
                "notes": notes,
                "mentions": []
            })
            script = f"if (window.setAutocompleteData) {{ window.setAutocompleteData({payload}); }}"
            self.webview.evaluate_javascript(script, -1, None, None, None, None)
        except Exception as e:
            print("Error syncing autocomplete data:", e)

    def _on_js_tag_clicked(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            tag = val.to_string() if hasattr(val, "to_string") else str(val)
            if tag:
                self.emit("tag-clicked", tag.strip().lstrip("#"))
        except Exception as e:
            print("Tag clicked error:", e)

    def _on_js_open_note_link(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            val_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if val_str:
                import json
                try:
                    data = json.loads(val_str)
                    title = data.get("title", "").strip()
                    heading = data.get("heading", "").strip()
                except Exception:
                    title = val_str.strip()
                    heading = ""
                self.emit("open-note-link", title, heading)
        except Exception as e:
            print("Open note link error:", e)

    def _on_js_open_external_url(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            uri = val.to_string() if hasattr(val, "to_string") else str(val)
            if uri:
                Gio.AppInfo.launch_default_for_uri(uri, None)
        except Exception as e:
            print("Failed to launch external URL:", e)

    def _on_decide_policy(self, _wv, decision, decision_type):
        if decision_type in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            action = decision.get_navigation_action()
            req = action.get_request() if action else None
            uri = req.get_uri() if req else None
            if uri and (uri.startswith("http://") or uri.startswith("https://") or uri.startswith("mailto:")):
                decision.ignore()
                try:
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except Exception as e:
                    print(f"Failed to open URI {uri}: {e}")
                return True
        return False

    def _on_js_insert_link(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            json_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if not json_str:
                return
            data = json.loads(json_str)
            initial_text = data.get("text", "") or ""
            initial_url = data.get("url", "") or "https://"
        except Exception as e:
            print("Error parsing insertLink message:", e)
            initial_text = ""
            initial_url = "https://"

        dialog = Adw.AlertDialog.new("Insert Link", None)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_response_appearance("insert", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("insert")
        dialog.set_close_response("cancel")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        grp = Adw.PreferencesGroup()

        label_row = Adw.EntryRow()
        label_row.set_title("Label")
        label_row.set_text(initial_text)
        label_row.set_activates_default(True)
        grp.add(label_row)

        url_row = Adw.EntryRow()
        url_row.set_title("URL")
        url_row.set_text(initial_url)
        url_row.set_activates_default(True)
        grp.add(url_row)

        box.append(grp)
        dialog.set_extra_child(box)

        def set_initial_focus():
            if initial_text:
                url_row.grab_focus()
                pos = len(url_row.get_text())
                if initial_url == "https://":
                    url_row.set_position(pos)
                else:
                    url_row.select_region(0, -1)
            else:
                label_row.grab_focus()
            return False

        GLib.idle_add(set_initial_focus)

        def on_response(_d, response):
            if response == "insert":
                label_val = label_row.get_text().strip()
                url_val = url_row.get_text().strip()
                if not url_val or url_val in ("https://", "http://"):
                    return
                # Normalize url if scheme missing
                if not any(url_val.lower().startswith(p) for p in ("http://", "https://", "mailto:", "ftp://", "file://", "#")):
                    url_val = "https://" + url_val
                if not label_val:
                    label_val = url_val

                script = f"if (window.applyInsertLink) {{ window.applyInsertLink({json.dumps(label_val)}, {json.dumps(url_val)}); }}"
                self.webview.evaluate_javascript(script, -1, None, None, None, None)
            else:
                script = "if (window.cancelInsertLink) { window.cancelInsertLink(); }"
                self.webview.evaluate_javascript(script, -1, None, None, None, None)

        dialog.connect("response", on_response)
        dialog.present(self.get_root() or self)

    def _on_js_category_selected(self, _ucm, js_result):
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            cat_name = val.to_string() if hasattr(val, "to_string") else str(val)
            cat_name = cat_name.strip().strip("/")
            if cat_name.lower() == "uncategorized":
                cat_name = ""
            if self.current_note:
                self.current_note.category = cat_name
                if self._pending_save_data:
                    self._pending_save_data["category"] = cat_name
                if cat_name:
                    self.db.create_category(cat_name)
                self.db.save_note(self.current_note.id, category=cat_name, sender=self)
                self.category_header_bar.set_category(cat_name)
                self.emit("note-category-changed", self.current_note.id, cat_name)
                self._sync_autocomplete_data()
        except Exception as e:
            print("Category selected error:", e)

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
                    note_tags = data.get("tags")
                    note_category = data.get("category", self.current_note.category if self.current_note else None)
                    if note_category and note_category.lower() == "uncategorized":
                        note_category = ""
                    self.db.save_note(
                        note_id=data["note_id"],
                        title=data["title"],
                        excerpt=data["excerpt"],
                        content_html=data["html"],
                        content_markdown=md_content,
                        category=note_category,
                        tags=note_tags,
                        has_todo=data["has_todo"],
                        sender=self
                    )
                    def on_done():
                        if self.current_note and self.current_note.id == data["note_id"]:
                            self.current_note.content_markdown = md_content
                        if self._pending_save_data and self._pending_save_data.get("html") == data["html"]:
                            self._pending_save_data = None
                            self.hide_conflict_banner()
                            self.status_label.set_text("Saved")
                            self.emit("note-updated", data["note_id"], data["title"], data["excerpt"], data["html"], md_content, data.get("tags", []), data["has_todo"])
                        return False

                    GLib.idle_add(on_done)
                except Exception as e:
                    print("Background save error:", e)

            threading.Thread(target=worker, daemon=True).start()
            return False

        self._save_timeout_id = GLib.timeout_add(250, do_save)

    def insert_tag(self, tag_name: str):
        """Insert a tag pill into the editor at cursor position."""
        clean = tag_name.strip().lstrip("#").lower()
        if not clean:
            return
        script = f"if (window.insertTag) {{ window.insertTag({json.dumps(clean)}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

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
                note_category = data.get("category", self.current_note.category if self.current_note else None)
                if note_category and note_category.lower() == "uncategorized":
                    note_category = ""
                note_tags = data.get("tags")
                self.db.save_note(
                    note_id=data["note_id"],
                    title=data["title"],
                    excerpt=data["excerpt"],
                    content_html=data["html"],
                    content_markdown=md,
                    category=note_category,
                    tags=note_tags,
                    has_todo=data["has_todo"],
                    sender=self
                )
                if self.current_note and self.current_note.id == data["note_id"]:
                    self.current_note.content_markdown = md
                self.hide_conflict_banner()
                self.status_label.set_text("Saved")
                self.emit("note-updated", data["note_id"], data["title"], data["excerpt"], data["html"], md, data.get("tags", []), data["has_todo"])
            except Exception as e:
                print("Flush save error:", e)

    def destroy_editor(self):
        """Clean up timers, pending saves, and WebKit handlers to avoid memory leaks."""
        self.flush_save()
        if self._save_timeout_id:
            GLib.source_remove(self._save_timeout_id)
            self._save_timeout_id = None
        if self._toolbar_reveal_timeout:
            GLib.source_remove(self._toolbar_reveal_timeout)
            self._toolbar_reveal_timeout = None
        if getattr(self, "_current_printer", None) is not None:
            self._current_printer = None
        if hasattr(self, "webview") and self.webview:
            try:
                ucm = self.webview.get_user_content_manager()
                # Disconnect signal handlers to prevent memory leaks
                for handler_id in getattr(self, "_message_handler_ids", []):
                    try:
                        ucm.disconnect(handler_id)
                    except Exception:
                        pass
                self._message_handler_ids = []
                for handler in [
                    "contentChanged", "statsChanged", "pickImage",
                    "uploadImage", "tagClicked", "openNoteLink", "categorySelected", "printNote",
                    "insertLink", "openExternalUrl"
                ]:
                    try:
                        ucm.unregister_script_message_handler(handler)
                    except Exception:
                        pass
            except Exception:
                pass

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
                    if getattr(self, "is_read_only", False):
                        self.set_read_only(False)
                    self.title_label.set_text(new_title)
                    script = f"""
                    (function() {{
                        var h1 = document.querySelector('h1');
                        if (h1) {{ h1.innerText = {json.dumps(new_title)}; }}
                        else {{
                            var newH1 = document.createElement('h1');
                            newH1.textContent = {json.dumps(new_title)};
                            var ed = document.getElementById('editor');
                            if (ed) {{ ed.insertBefore(newH1, ed.firstChild); }}
                        }}
                        notifyChange();
                    }})();
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
            self.flush_save()
            export_note_dialog(window, self.current_note, fmt, db=self.db)

    def _on_page_setup(self, window: Optional[Gtk.Window] = None):
        """Show Page Setup dialog to configure paper size, orientation, and margins."""
        parent = window if isinstance(window, Gtk.Window) else self.get_root()
        if not isinstance(parent, Gtk.Window):
            parent = None

        current_unit = "in"
        if hasattr(self.config_manager, "get_page_setup_unit"):
            current_unit = self.config_manager.get_page_setup_unit()

        def on_applied(new_setup, unit):
            self.page_setup = new_setup
            if hasattr(self.config_manager, "set_page_setup"):
                self.config_manager.set_page_setup(new_setup, unit)
            top_win = self.get_root()
            if top_win and hasattr(top_win, "index_view") and hasattr(top_win.index_view, "toast_overlay"):
                top_win.index_view.toast_overlay.add_toast(Adw.Toast.new("Page setup saved"))

        show_page_setup_dialog(
            parent_window=parent,
            current_page_setup=getattr(self, "page_setup", None),
            current_unit=current_unit,
            on_applied=on_applied,
        )

    def _print_note(self, window: Optional[Gtk.Window] = None):
        if not self.current_note:
            return
        if getattr(self, "_current_printer", None) is not None:
            return
        self.flush_save()
        parent = window if isinstance(window, Gtk.Window) else self.get_root()
        if not isinstance(parent, Gtk.Window):
            parent = None
        printer = Printer(self.current_note, db=self.db, parent_window=parent, page_setup=getattr(self, "page_setup", None))
        self._current_printer = printer
        printer.connect("finished", lambda _p: setattr(self, "_current_printer", None))
        try:
            printer.print()
        except Exception as e:
            print("Failed to start printer:", e)
            self._current_printer = None

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

    def _update_lock_ui(self):
        is_locked = bool(self.current_note and self.current_note.is_locked)
        if hasattr(self, "lock_btn"):
            self.lock_btn.set_visible(is_locked)
        if hasattr(self, "more_btn"):
            self.more_btn.set_menu_model(self._create_more_menu())
            more_popover = self.more_btn.get_popover()
            if more_popover:
                if hasattr(self, "theme_selector"):
                    more_popover.add_child(self.theme_selector, "theme")
                if hasattr(self, "font_size_selector"):
                    more_popover.add_child(self.font_size_selector, "fontsize")

    def _on_lock_clicked(self):
        """Immediately lock private notes and exit back to notes view."""
        top_win = self.get_root()
        if top_win:
            if hasattr(top_win, "index_view"):
                if getattr(top_win.index_view, "notes_list", None) and top_win.index_view.notes_list.selection_mode:
                    top_win.index_view.exit_selection_mode()
                if getattr(top_win.index_view, "header_stack", None) and top_win.index_view.header_stack.get_visible_child_name() == "search":
                    top_win.index_view.exit_search()
                top_win.index_view._private_unlocked = False
                top_win.index_view.refresh()
            if hasattr(top_win, "_go_back"):
                top_win._go_back()
            if hasattr(top_win, "index_view") and hasattr(top_win.index_view, "toast_overlay"):
                top_win.index_view.toast_overlay.add_toast(Adw.Toast.new("Private notes locked"))

    def _set_current_note_locked(self, locked: bool):
        if not self.current_note:
            return
        self.db.set_note_locked(self.current_note.id, locked, sender=self)
        self.current_note.is_locked = locked
        self._update_lock_ui()
        top_win = self.get_root()
        if top_win and hasattr(top_win, "index_view") and hasattr(top_win.index_view, "toast_overlay"):
            msg = "Note locked as Private" if locked else "Removed from Private Notes"
            top_win.index_view.toast_overlay.add_toast(Adw.Toast.new(msg))

    def _on_toggle_lock(self):
        if not self.current_note:
            return

        window = self.get_root()
        is_currently_locked = bool(self.current_note.is_locked)

        if not is_currently_locked:
            if not self.db.has_private_password():
                dlg = Adw.AlertDialog.new(
                    "Set Private Note Password",
                    "Please set a master password to protect your private notes."
                )
                dlg.add_response("cancel", "Cancel")
                dlg.add_response("save", "Set Password & Lock")
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
                    self._set_current_note_locked(True)

                dlg.connect("response", on_set_pwd_res)
                dlg.present(window or self)
            else:
                self._set_current_note_locked(True)
        else:
            # Already authenticated in unlocked session: remove lock without asking for password again
            self._set_current_note_locked(False)

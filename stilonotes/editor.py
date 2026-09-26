# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
from typing import Optional

import gi
gi.require_version('WebKit', '6.0')
from gi.repository import Adw, Gtk, WebKit, Gio, GLib, GObject, Gdk, Pango

from stilonotes.category_header_bar import CategoryHeaderBar
from stilonotes.models import Note
from stilonotes.editor_html import get_editor_html_page
from stilonotes.markdown_utils import format_relative_date, html_to_markdown
from stilonotes.exporter import export_note_dialog
from stilonotes.const import get_assets_path


class FormattingBar(Gtk.Box):
    """Bottom formatting toolbar — mirrors Iotas FormattingHeaderBar style."""

    __gtype_name__ = "StiloFormattingBar"

    def __init__(self, exec_fn):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._exec = exec_fn
        self._build()

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

        # Heading menu button
        heading_menu = Gtk.MenuButton()
        heading_menu.set_icon_name("format-text-larger-symbolic")
        heading_menu.set_tooltip_text("Heading")
        heading_menu.set_focus_on_click(False)
        heading_menu.add_css_class("flat")

        h_pop = Gtk.Popover()
        h_pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h_pop_box.set_margin_start(4)
        h_pop_box.set_margin_end(4)
        h_pop_box.set_margin_top(4)
        h_pop_box.set_margin_bottom(4)
        for lbl, cmd in [("Heading 1", "heading1"), ("Heading 2", "heading2"),
                         ("Heading 3", "heading3"), ("Paragraph", "paragraph")]:
            b = Gtk.Button(label=lbl)
            b.add_css_class("flat")
            b.connect("clicked", lambda _b, c=cmd: (h_pop.popdown(), self._exec(c)))
            h_pop_box.append(b)
        h_pop.set_child(h_pop_box)
        heading_menu.set_popover(h_pop)
        parent_box.append(heading_menu)

        self._add_sep(parent_box)

        for icon, tip, cmd in [
            ("format-text-bold-symbolic",          "Bold",          "bold"),
            ("format-text-italic-symbolic",        "Italic",        "italic"),
            ("format-text-strikethrough-symbolic", "Strikethrough", "strike"),
            ("format-text-underline-symbolic",     "Underline",     "underline"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

        self._add_sep(parent_box)

        for icon, tip, cmd in [
            ("view-list-bullet-symbolic",  "Bullet List",   "bullet"),
            ("view-list-ordered-symbolic", "Numbered List", "number"),
            ("checkbox-checked-symbolic",  "Checklist",     "todo"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

        self._add_sep(parent_box)

        for icon, tip, cmd in [
            ("quotation-symbolic",       "Blockquote",      "quote"),
            ("code-symbolic",            "Code Block",      "code"),
            ("insert-link-symbolic",     "Insert Link",     "link"),
            ("view-continuous-symbolic", "Horizontal Rule", "divider"),
        ]:
            self._add_btn(parent_box, icon, tip, cmd)

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
        self.current_note: Optional[Note] = None
        self.is_dark_mode = False
        self.latest_stats = {"words": 0, "chars": 0, "paragraphs": 0, "readTime": "1 min"}
        self._toolbar_reveal_timeout = None
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

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.set_valign(Gtk.Align.CENTER)

        self.title_button = Gtk.Button()
        self.title_button.add_css_class("flat")
        self.title_button.add_css_class("stilo-editor-title-btn")
        self.title_label = Gtk.Label(label="Untitled Note")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(32)
        self.title_button.set_child(self.title_label)
        self.title_button.connect("clicked", self._on_title_clicked)
        title_box.append(self.title_button)

        self.status_label = Gtk.Label(label="")
        self.status_label.add_css_class("stilo-status-label")
        title_box.append(self.status_label)

        self.main_header_bar.set_title_widget(title_box)

        # Stats button
        self.stats_popover = self._create_stats_popover()
        self.info_btn = Gtk.MenuButton()
        self.info_btn.set_icon_name("dialog-information-symbolic")
        self.info_btn.set_tooltip_text("Note Statistics")
        self.info_btn.set_popover(self.stats_popover)
        self.main_header_bar.pack_end(self.info_btn)

        # Editor menu (more)
        self.more_btn = Gtk.MenuButton()
        self.more_btn.set_icon_name("view-more-symbolic")
        self.more_btn.set_tooltip_text("Editor Menu")
        self.more_btn.set_menu_model(self._create_more_menu())
        self.main_header_bar.pack_end(self.more_btn)

        # Star / Favorites toggle button
        self.star_btn = Gtk.Button()
        self.star_btn.set_icon_name("non-starred-symbolic")
        self.star_btn.set_tooltip_text("Pin to Favorites")
        self.star_btn.add_css_class("flat")
        self.star_btn.connect("clicked", lambda _b: self._on_toggle_pin())
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

        bg_rgba = Gdk.RGBA()
        bg_rgba.parse("#24252A" if self.is_dark_mode else "#FFFFFF")
        self.webview.set_background_color(bg_rgba)

        settings = self.webview.get_settings()
        try:
            settings.set_enable_javascript(True)
            settings.set_enable_developer_extras(True)
            settings.set_allow_file_access_from_file_urls(True)
            settings.set_allow_universal_access_from_file_urls(True)
        except Exception:
            pass

        self._setup_message_handlers()

        initial_html = get_editor_html_page("", self.is_dark_mode)
        assets_uri = f"file://{get_assets_path()}/"
        self.webview.load_html(initial_html, assets_uri)

        overlay.set_child(self.webview)

        # Bottom formatting bar in revealer
        self.fmt_bar = FormattingBar(self._exec_js_format)

        self.fmt_revealer = Gtk.Revealer()
        self.fmt_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.fmt_revealer.set_transition_duration(250)
        self.fmt_revealer.set_valign(Gtk.Align.END)
        self.fmt_revealer.set_halign(Gtk.Align.FILL)
        self.fmt_revealer.set_hexpand(True)
        self.fmt_revealer.set_reveal_child(True)
        self.fmt_revealer.set_child(self.fmt_bar)
        overlay.add_overlay(self.fmt_revealer)

        # Mouse motion for auto-hide
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_webview_motion)
        motion.connect("leave", self._on_webview_leave)
        self.webview.add_controller(motion)

        self.append(overlay)

    # ── Toolbar auto-hide ─────────────────────────────────────────────────

    def _on_webview_motion(self, ctrl, x, y):
        h = self.webview.get_height()
        if h > 0 and y >= h - 120:
            self._show_toolbar()
        else:
            self._schedule_hide_toolbar()

    def _on_webview_leave(self, ctrl):
        self._schedule_hide_toolbar()

    def _show_toolbar(self):
        if self._toolbar_reveal_timeout:
            GLib.source_remove(self._toolbar_reveal_timeout)
            self._toolbar_reveal_timeout = None
        self.fmt_revealer.set_reveal_child(True)

    def _schedule_hide_toolbar(self):
        if self._toolbar_reveal_timeout:
            return
        def do_hide():
            self.fmt_revealer.set_reveal_child(False)
            self._toolbar_reveal_timeout = None
            return False
        self._toolbar_reveal_timeout = GLib.timeout_add(1500, do_hide)

    # ── WebKit message handlers ───────────────────────────────────────────

    def _setup_message_handlers(self):
        ucm = self.webview.get_user_content_manager()
        try:
            ucm.register_script_message_handler("contentChanged")
            ucm.connect("script-message-received::contentChanged", self._on_js_content_changed)
            ucm.register_script_message_handler("pickImage")
            ucm.connect("script-message-received::pickImage", self._on_js_pick_image)
        except Exception as e:
            print("Message handler registration error:", e)

    # ── Stats popover ─────────────────────────────────────────────────────

    def _create_stats_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
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

        s1 = Gio.Menu()
        s1.append("Toggle Dark Theme",  "editor.toggle-theme")
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

        act("rename-title",  lambda: self._on_title_clicked(None))
        act("edit-category", self.enter_edit_category)
        act("toggle-pin",    self._on_toggle_pin)
        act("duplicate",     self._on_duplicate)
        act("toggle-theme",  lambda: self.emit("toggle-app-theme"))
        act("show-stats",    lambda: self.info_btn.popup())
        act("export-md",     lambda: self._export_note("md",   window))
        act("export-html",   lambda: self._export_note("html", window))
        act("export-txt",    lambda: self._export_note("txt",  window))
        act("delete",        self._on_delete)

        self.insert_action_group("editor", ag)

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
        self.current_note = note
        self.header_stack.set_visible_child_name("main")
        self.title_label.set_text(note.title)
        self.status_label.set_text("Saved")

        # Update star button state
        self._update_star_btn(note.is_pinned)

        html_content = note.content_html or f"<h1>{note.title}</h1><div><br></div>"
        escaped_html = json.dumps(html_content)
        script = f"if (window.setEditorContent) {{ window.setEditorContent({escaped_html}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

        self._show_toolbar()
        self.update_stats_popover()

    def update_theme(self, is_dark: bool):
        self.is_dark_mode = is_dark
        bg_rgba = Gdk.RGBA()
        bg_rgba.parse("#24252A" if is_dark else "#FFFFFF")
        self.webview.set_background_color(bg_rgba)
        script = f"if (window.setEditorTheme) {{ window.setEditorTheme({'true' if is_dark else 'false'}); }}"
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
        script = f"window.execFormatting('{command}');"
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
            self.status_label.set_text("Saved")

            new_md = html_to_markdown(new_html)
            self.emit("note-updated",
                      self.current_note.id, new_title, new_excerpt,
                      new_html, new_md, [], has_todo)
            self.update_stats_popover()
        except Exception as e:
            print("Error parsing content change:", e)

    def _on_js_pick_image(self, _ucm, _js_result):
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
                if f:
                    uri = f.get_uri()
                    script = f"insertImageAtCursor('{uri}');"
                    self.webview.evaluate_javascript(script, -1, None, None, None, None)
            except Exception:
                pass

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

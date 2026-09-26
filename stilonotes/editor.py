# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
from typing import Optional, Dict, Any

import gi
gi.require_version('WebKit', '6.0')
from gi.repository import Adw, Gtk, WebKit, Gio, GLib, GObject, Gdk, Pango

from stilonotes.category_header_bar import CategoryHeaderBar
from stilonotes.models import Note
from stilonotes.editor_html import get_editor_html_page
from stilonotes.markdown_utils import format_relative_date, html_to_markdown
from stilonotes.exporter import export_note_dialog
from stilonotes.const import get_assets_path

class NoteEditor(Gtk.Box):
    __gtype_name__ = "NoteEditor"

    __gsignals__ = {
        "note-updated": (GObject.SignalFlags.RUN_FIRST, None, (str, str, str, str, str, object, bool)),
        "note-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-duplicated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-category-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "back": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, db):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.current_note: Optional[Note] = None
        self.is_dark_mode = False
        self.latest_stats = {
            "words": 0,
            "chars": 0,
            "paragraphs": 0,
            "readTime": "1 min"
        }

        self._build_ui()

    def _build_ui(self):
        # 1. Header Stack: Main HeaderBar and Category HeaderBar
        self.header_stack = Gtk.Stack()
        self.header_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Main HeaderBar
        self.main_header_bar = Adw.HeaderBar()
        self.main_header_bar.set_show_back_button(False)
        self.main_header_bar.set_show_end_title_buttons(True)
        self.main_header_bar.set_show_start_title_buttons(False)

        # Back button
        self.back_btn = Gtk.Button()
        self.back_btn.set_icon_name("go-previous-symbolic")
        self.back_btn.set_tooltip_text("Back to Notes (Esc / Alt+Left)")
        self.back_btn.connect("clicked", lambda _b: self.emit("back"))
        self.main_header_bar.pack_start(self.back_btn)

        # Title Box
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

        # Format button with popover
        self.format_btn = Gtk.MenuButton()
        self.format_btn.set_icon_name("format-text-bold-symbolic")
        self.format_btn.set_tooltip_text("Text Formatting")
        self.format_btn.set_popover(self._create_format_popover())
        self.main_header_bar.pack_end(self.format_btn)

        # Info / Stats button
        self.stats_popover = self._create_stats_popover()
        self.info_btn = Gtk.MenuButton()
        self.info_btn.set_icon_name("dialog-information-symbolic")
        self.info_btn.set_tooltip_text("Note Information & Statistics")
        self.info_btn.set_popover(self.stats_popover)
        self.main_header_bar.pack_end(self.info_btn)

        # Theme toggle button
        self.theme_btn = Gtk.Button()
        self.theme_btn.set_icon_name("weather-clear-night-symbolic")
        self.theme_btn.set_tooltip_text("Toggle Theme (Dark / Light)")
        self.theme_btn.connect("clicked", self._on_toggle_theme)
        self.main_header_bar.pack_end(self.theme_btn)

        # More menu button
        self.more_btn = Gtk.MenuButton()
        self.more_btn.set_icon_name("view-more-symbolic")
        self.more_btn.set_tooltip_text("More Options")
        self.more_btn.set_menu_model(self._create_more_menu())
        self.main_header_bar.pack_end(self.more_btn)

        self.header_stack.add_named(self.main_header_bar, "main")

        # Category HeaderBar (for changing / selecting / removing category)
        self.category_header_bar = CategoryHeaderBar()
        self.category_header_bar.connect("category-changed", self._on_category_changed)
        self.category_header_bar.connect("abort", self._on_abort_category_change)
        self.header_stack.add_named(self.category_header_bar, "category")

        self.append(self.header_stack)

        # 2. WebKit WebView
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

        self.append(self.webview)

    def _setup_message_handlers(self):
        """Register WebKit user content script message handlers."""
        ucm = self.webview.get_user_content_manager()
        try:
            ucm.register_script_message_handler("contentChanged")
            ucm.connect("script-message-received::contentChanged", self._on_js_content_changed)

            ucm.register_script_message_handler("pickImage")
            ucm.connect("script-message-received::pickImage", self._on_js_pick_image)
        except Exception as e:
            print("Message handler registration error:", e)

    def _create_format_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        # Headings row
        h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for label, cmd in [("H1", "heading1"), ("H2", "heading2"), ("H3", "heading3"), ("P", "paragraph")]:
            btn = Gtk.Button(label=label)
            btn.add_css_class("flat")
            btn.connect("clicked", lambda _b, c=cmd: self._exec_js_format(c))
            h_box.append(btn)
        box.append(h_box)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Inline row
        fmt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        b_btn = Gtk.Button(label="B")
        b_btn.add_css_class("flat")
        b_btn.connect("clicked", lambda _b: self._exec_js_format("bold"))
        fmt_box.append(b_btn)

        i_btn = Gtk.Button(label="I")
        i_btn.add_css_class("flat")
        i_btn.connect("clicked", lambda _b: self._exec_js_format("italic"))
        fmt_box.append(i_btn)

        s_btn = Gtk.Button(label="S")
        s_btn.add_css_class("flat")
        s_btn.connect("clicked", lambda _b: self._exec_js_format("strike"))
        fmt_box.append(s_btn)

        hl_btn = Gtk.Button(label="🖍️")
        hl_btn.add_css_class("flat")
        hl_btn.connect("clicked", lambda _b: self._exec_js_format("highlight"))
        fmt_box.append(hl_btn)

        box.append(fmt_box)
        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Blocks
        for title, cmd, icon in [
            ("Todo Checklist", "todo", "view-list-bullet-symbolic"),
            ("Bullet List", "bullet", "view-list-symbolic"),
            ("Numbered List", "number", "view-list-ordered-symbolic"),
            ("Code Block", "code", "text-x-generic-symbolic"),
            ("Blockquote", "quote", "format-indent-more-symbolic"),
            ("Table", "table", "view-grid-symbolic"),
            ("Horizontal Divider", "divider", "list-remove-symbolic"),
            ("Insert Link", "link", "insert-link-symbolic"),
        ]:
            item_btn = Gtk.Button()
            item_btn.add_css_class("flat")
            item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            item_box.append(Gtk.Image.new_from_icon_name(icon))
            item_box.append(Gtk.Label(label=title))
            item_btn.set_child(item_box)
            item_btn.connect("clicked", lambda _b, c=cmd: self._exec_js_format(c))
            box.append(item_btn)

        popover.set_child(box)
        return popover

    def _exec_js_format(self, command: str):
        script = f"window.execFormatting('{command}');"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

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

        labels = [
            ("Words:", "words_val"),
            ("Characters:", "chars_val"),
            ("Paragraphs:", "paras_val"),
            ("Reading Time:", "read_val"),
            ("Created:", "created_val"),
            ("Modified:", "modified_val"),
        ]

        self.stat_val_labels = {}
        for r, (txt, key) in enumerate(labels):
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

    def _create_more_menu(self) -> Gio.Menu:
        menu = Gio.Menu()

        section1 = Gio.Menu()
        section1.append("Edit Title…", "editor.rename-title")
        section1.append("Change Category…", "editor.edit-category")
        section1.append("Toggle Pin", "editor.toggle-pin")
        section1.append("Duplicate Note", "editor.duplicate")
        menu.append_section(None, section1)

        section2 = Gio.Menu()
        section2.append("Export as Markdown…", "editor.export-md")
        section2.append("Export as HTML…", "editor.export-html")
        section2.append("Export as Plain Text…", "editor.export-txt")
        menu.append_section(None, section2)

        section3 = Gio.Menu()
        section3.append("Delete Note", "editor.delete")
        menu.append_section(None, section3)

        return menu

    def setup_actions(self, window: Gtk.Window):
        """Connect actions for more menu."""
        action_group = Gio.SimpleActionGroup()

        rename_action = Gio.SimpleAction.new("rename-title", None)
        rename_action.connect("activate", lambda _a, _p: self._on_title_clicked(None))
        action_group.add_action(rename_action)

        edit_cat_action = Gio.SimpleAction.new("edit-category", None)
        edit_cat_action.connect("activate", lambda _a, _p: self.enter_edit_category())
        action_group.add_action(edit_cat_action)

        pin_action = Gio.SimpleAction.new("toggle-pin", None)
        pin_action.connect("activate", lambda _a, _p: self._on_toggle_pin())
        action_group.add_action(pin_action)

        dup_action = Gio.SimpleAction.new("duplicate", None)
        dup_action.connect("activate", lambda _a, _p: self._on_duplicate())
        action_group.add_action(dup_action)

        exp_md_action = Gio.SimpleAction.new("export-md", None)
        exp_md_action.connect("activate", lambda _a, _p: self._export_note("md", window))
        action_group.add_action(exp_md_action)

        exp_html_action = Gio.SimpleAction.new("export-html", None)
        exp_html_action.connect("activate", lambda _a, _p: self._export_note("html", window))
        action_group.add_action(exp_html_action)

        exp_txt_action = Gio.SimpleAction.new("export-txt", None)
        exp_txt_action.connect("activate", lambda _a, _p: self._export_note("txt", window))
        action_group.add_action(exp_txt_action)

        del_action = Gio.SimpleAction.new("delete", None)
        del_action.connect("activate", lambda _a, _p: self._on_delete())
        action_group.add_action(del_action)

        self.insert_action_group("editor", action_group)

    def enter_edit_category(self):
        """Show category headerbar for selecting or editing categories."""
        if not self.current_note:
            return
        categories = [c.name for c in self.db.get_categories()]
        self.category_header_bar.set_categories(categories)
        self.header_stack.set_visible_child_name("category")
        self.category_header_bar.activate(self.current_note.category or "")

    def _on_category_changed(self, _bar, new_category: str):
        """Handle category applied or cleared."""
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
        """Revert / abort category editing."""
        self.header_stack.set_visible_child_name("main")

    def load_note(self, note: Note):
        """Load note into WebKit view."""
        self.current_note = note
        self.header_stack.set_visible_child_name("main")
        self.title_label.set_text(note.title)
        self.status_label.set_text("Saved")

        html_content = note.content_html or f"<h1>{note.title}</h1><div><br></div>"
        escaped_html = json.dumps(html_content)
        script = f"if (window.setEditorContent) {{ window.setEditorContent({escaped_html}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

        self.update_stats_popover()

    def update_theme(self, is_dark: bool):
        self.is_dark_mode = is_dark
        self.theme_btn.set_icon_name("weather-clear-symbolic" if is_dark else "weather-clear-night-symbolic")

        bg_rgba = Gdk.RGBA()
        bg_rgba.parse("#24252A" if is_dark else "#FFFFFF")
        self.webview.set_background_color(bg_rgba)

        script = f"if (window.setEditorTheme) {{ window.setEditorTheme({'true' if is_dark else 'false'}); }}"
        self.webview.evaluate_javascript(script, -1, None, None, None, None)

    def _on_toggle_theme(self, _btn):
        new_theme = not self.is_dark_mode
        self.update_theme(new_theme)

    def _on_js_content_changed(self, _ucm, js_result):
        """Handle contentChanged message from WebKit."""
        try:
            val = js_result.get_js_value() if hasattr(js_result, "get_js_value") else js_result
            json_str = val.to_string() if hasattr(val, "to_string") else str(val)
            if not json_str:
                return
            data = json.loads(json_str)

            if not self.current_note:
                return

            new_title = data.get("title", self.current_note.title)
            new_excerpt = data.get("excerpt", self.current_note.excerpt)
            new_html = data.get("html", self.current_note.content_html)
            new_tags = data.get("tags", self.current_note.tags)
            stats = data.get("stats", {})
            has_todo = data.get("has_todo", False)

            self.latest_stats = stats
            self.title_label.set_text(new_title)
            self.status_label.set_text("Saved")

            new_md = html_to_markdown(new_html)

            self.emit(
                "note-updated",
                self.current_note.id,
                new_title,
                new_excerpt,
                new_html,
                new_md,
                [],
                has_todo
            )
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

        root_win = self.get_root()
        dialog.open(root_win, None, on_open_finish)

    def _on_title_clicked(self, _btn):
        if not self.current_note:
            return

        dialog = Adw.AlertDialog.new(
            "Rename Note",
            "Enter a new title for this note:"
        )
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
        parent = self.get_root() or self
        dialog.present(parent)

    def _on_toggle_pin(self):
        if self.current_note:
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

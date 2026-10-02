# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gio, Gdk, GLib

from stilonotes.const import APP_ID, APP_NAME, VERSION, get_assets_path
from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.window import StiloWindow

class StiloApplication(Adw.Application):
    __gtype_name__ = "StiloApplication"

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.db: Optional[NoteDatabase] = None
        self.config_manager: Optional[ConfigManager] = None

    def create_window(self) -> StiloWindow:
        """Create and return a new application window sharing the database and config."""
        if not self.db:
            self.db = NoteDatabase()
        if not self.config_manager:
            self.config_manager = ConfigManager.get_default(self.db)
        return StiloWindow(self, self.db)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._setup_icons()
        self._load_css()
        self._setup_actions()

    def _setup_icons(self):
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icons_dir = get_assets_path() / "icons"
            if icons_dir.exists():
                icon_theme.add_search_path(str(icons_dir))

    def do_activate(self):
        if not self.db:
            self.db = NoteDatabase()
        self.config_manager = ConfigManager.get_default(self.db)

        windows = self.get_windows()
        if not windows:
            win = self.create_window()
            win.present()
        else:
            active_win = self.get_active_window() or windows[0]
            active_win.present()

    def do_shutdown(self):
        """Cleanly close all window resources and database on application quit."""
        for win in list(self.get_windows()):
            if hasattr(win, "_cleanup"):
                try:
                    win._cleanup()
                except Exception:
                    pass
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        Gio.Application.do_shutdown(self)

    def _load_css(self):
        css_path = get_assets_path() / "css" / "style.css"
        if css_path.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(css_path))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                print("Error loading CSS:", e)

    def _setup_actions(self):
        def add_simple_action(name, callback, accels=None):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

        add_simple_action("new-window", self._on_new_window, ["<Control><Shift>n"])
        add_simple_action("about", self._on_about)
        add_simple_action("preferences", self._on_preferences, ["<Control>comma"])
        add_simple_action("shortcuts", self._on_shortcuts, ["<Control>question"])
        add_simple_action("quit", lambda _a, _p: self.quit(), ["<Control>q"])

    def _on_new_window(self, _action, _param):
        win = self.create_window()
        win.present()

    def _on_about(self, _action, _param):
        about = Adw.AboutDialog()
        about.set_application_name(APP_NAME)
        about.set_application_icon(APP_ID)
        about.set_version(VERSION)
        about.set_developer_name("Mohammed Asif Ali Rizvan")
        about.set_developers(["Mohammed Asif Ali Rizvan <fast.rizwaan@gmail.com>"])
        about.set_artists(["Mohammed Asif Ali Rizvan"])
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments("Iotas inspired rich text notes with dynamic WebKit Markdown rendering")
        about.set_website("https://github.com/fastrizwaan/StiloNotes")
        about.set_issue_url("https://github.com/fastrizwaan/StiloNotes/issues")

        parent = self.get_active_window()
        about.present(parent)

    def _on_preferences(self, _action, _param):
        parent = self.get_active_window()
        dialog = Adw.PreferencesDialog()
        dialog.set_title("Preferences")

        # ── Page 1: General ───────────────────────────────────────────────────
        page_general = Adw.PreferencesPage()
        page_general.set_title("General")
        page_general.set_icon_name("preferences-system-symbolic")

        # Appearance Group
        group_app = Adw.PreferencesGroup()
        group_app.set_title("Appearance")
        group_app.set_description("Customize how Stilo Notes looks and behaves")

        theme_row = Adw.ComboRow()
        theme_row.set_title("Color Scheme")
        theme_row.set_model(Gtk.StringList.new(["Follow System", "Light", "Dark"]))

        style_manager = Adw.StyleManager.get_default()
        cur_scheme = style_manager.get_color_scheme()
        if cur_scheme == Adw.ColorScheme.FORCE_LIGHT:
            theme_row.set_selected(1)
        elif cur_scheme == Adw.ColorScheme.FORCE_DARK:
            theme_row.set_selected(2)
        else:
            theme_row.set_selected(0)

        def on_theme_changed(row, _param):
            idx = row.get_selected()
            if idx == 1:
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("light")
            elif idx == 2:
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("dark")
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("follow")

        theme_row.connect("notify::selected", on_theme_changed)
        group_app.add(theme_row)

        # Editor Mode Row
        editor_mode_row = Adw.ComboRow()
        editor_mode_row.set_title("Editor View Mode")
        editor_mode_row.set_subtitle("Sidebar visibility while editing a note")
        editor_mode_row.set_model(Gtk.StringList.new([
            "Distraction-Free (Hide sidebar)",
            "Standard (Keep sidebar visible)"
        ]))
        cur_mode = self.config_manager.get_editor_mode() if hasattr(self, "config_manager") else "distraction_free"
        editor_mode_row.set_selected(0 if cur_mode == "distraction_free" else 1)

        def on_editor_mode_changed(row, _param):
            mode = "distraction_free" if row.get_selected() == 0 else "standard"
            if hasattr(self, "config_manager"):
                self.config_manager.set_editor_mode(mode)
            for win in self.get_windows():
                if hasattr(win, "apply_editor_mode"):
                    win.apply_editor_mode(mode)

        editor_mode_row.connect("notify::selected", on_editor_mode_changed)
        group_app.add(editor_mode_row)
        page_general.add(group_app)

        # Storage group
        group_storage = Adw.PreferencesGroup()
        group_storage.set_title("Storage")
        path_row = Adw.ActionRow()
        path_row.set_title("Database Location")
        if self.db:
            path_row.set_subtitle(str(self.db.db_path))
        group_storage.add(path_row)
        page_general.add(group_storage)
        dialog.add(page_general)

        # ── Page 2: Typography ────────────────────────────────────────────────
        page_typo = Adw.PreferencesPage()
        page_typo.set_title("Typography")
        page_typo.set_icon_name("font-x-generic-symbolic")

        def notify_windows_typography():
            for win in self.get_windows():
                if hasattr(win, "editor"):
                    if hasattr(win.editor, "update_typography"):
                        win.editor.update_typography()
                    if hasattr(win.editor, "font_size_selector"):
                        win.editor.font_size_selector.refresh()

        def notify_windows_card_size(size_str: str):
            for win in self.get_windows():
                if hasattr(win, "apply_card_size"):
                    win.apply_card_size(size_str)

        # Group 1: Notes List & Cards
        group_cards = Adw.PreferencesGroup()
        group_cards.set_title("Notes List &amp; Cards")
        group_cards.set_description("Font size for note card titles, dates, and previews")

        card_size_row = Adw.ComboRow()
        if hasattr(card_size_row, "set_use_markup"):
            card_size_row.set_use_markup(False)
        card_size_row.set_title("Card & List Text Size")
        card_size_row.set_model(Gtk.StringList.new([
            "Small (85%)",
            "Normal (Default)",
            "Large (120%)",
            "Extra Large (140%)"
        ]))
        card_size_keys = ["small", "default", "large", "xlarge"]
        cur_card_size = self.config_manager.get_card_font_size() if hasattr(self, "config_manager") else "default"
        card_size_idx = card_size_keys.index(cur_card_size) if cur_card_size in card_size_keys else 1
        card_size_row.set_selected(card_size_idx)

        def on_card_size_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(card_size_keys):
                selected = card_size_keys[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_card_font_size(selected)
                notify_windows_card_size(selected)

        card_size_row.connect("notify::selected", on_card_size_changed)
        group_cards.add(card_size_row)
        page_typo.add(group_cards)

        # Group 2: Note Content
        group_editor = Adw.PreferencesGroup()
        group_editor.set_title("Note Content")
        group_editor.set_description("Typeface and zoom level for note body, headings, code, and quotes")

        font_family_row = Adw.ComboRow()
        font_family_row.set_title("Font Family")
        font_family_row.set_subtitle("Typeface for note content and headings")
        font_family_row.set_model(Gtk.StringList.new([
            "System (Default)",
            "Sans-Serif",
            "Serif",
            "Monospace"
        ]))
        font_family_keys = ["system", "sans", "serif", "monospace"]
        cur_font_family = self.config_manager.get_font_family() if hasattr(self, "config_manager") else "system"
        font_family_idx = font_family_keys.index(cur_font_family) if cur_font_family in font_family_keys else 0
        font_family_row.set_selected(font_family_idx)

        def on_font_family_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(font_family_keys):
                selected_family = font_family_keys[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_font_family(selected_family)
                notify_windows_typography()

        font_family_row.connect("notify::selected", on_font_family_changed)
        group_editor.add(font_family_row)

        editor_size_row = Adw.ComboRow()
        editor_size_row.set_title("Note Text Size")
        editor_size_row.set_subtitle("Zoom percentage for note content")
        editor_size_row.set_model(Gtk.StringList.new([
            "80%",
            "90%",
            "100% (Default)",
            "110%",
            "120%",
            "130%",
            "140%",
            "150%",
            "160%"
        ]))
        editor_percent_values = [80, 90, 100, 110, 120, 130, 140, 150, 160]
        cur_percent = self.config_manager.get_editor_zoom_percent() if hasattr(self, "config_manager") else 100
        editor_size_idx = editor_percent_values.index(cur_percent) if cur_percent in editor_percent_values else 2
        editor_size_row.set_selected(editor_size_idx)

        def on_editor_size_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(editor_percent_values):
                selected_pct = editor_percent_values[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_editor_zoom_percent(selected_pct)
                notify_windows_typography()

        editor_size_row.connect("notify::selected", on_editor_size_changed)
        group_editor.add(editor_size_row)
        page_typo.add(group_editor)

        # Group 3: Reset to Defaults
        group_reset = Adw.PreferencesGroup()
        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset to Defaults")
        reset_row.set_subtitle("Restore default font family, text sizes, and zoom")
        reset_btn = Gtk.Button(label="Reset to Defaults")
        reset_btn.add_css_class("suggested-action")
        reset_btn.set_valign(Gtk.Align.CENTER)

        def on_reset_typography(_b):
            if hasattr(self, "config_manager"):
                self.config_manager.reset_typography_defaults()
            card_size_row.set_selected(1)
            font_family_row.set_selected(0)
            editor_size_row.set_selected(2)
            notify_windows_card_size("default")
            notify_windows_typography()

        reset_btn.connect("clicked", on_reset_typography)
        reset_row.add_suffix(reset_btn)
        reset_row.set_activatable_widget(reset_btn)
        group_reset.add(reset_row)
        page_typo.add(group_reset)
        dialog.add(page_typo)

        dialog.present(parent)

    def _on_shortcuts(self, _action, _param):
        parent = self.get_active_window()
        builder = Gtk.Builder()

        shortcuts_xml = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkShortcutsWindow" id="shortcuts_window">
    <property name="modal">True</property>
    <child>
      <object class="GtkShortcutsSection">
        <property name="visible">True</property>
        <property name="section-name">shortcuts</property>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="visible">True</property>
            <property name="title">General</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;&lt;Shift&gt;n</property>
                <property name="title">New window</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;n</property>
                <property name="title">Create new note</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;f</property>
                <property name="title">Search notes</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;backslash</property>
                <property name="title">Toggle sidebar folders</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;&lt;Shift&gt;d</property>
                <property name="title">Toggle dark / light theme</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">Escape</property>
                <property name="title">Go back to notes list</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;q</property>
                <property name="title">Quit application</property>
              </object>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="visible">True</property>
            <property name="title">Editor Formatting</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;b</property>
                <property name="title">Bold text</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;i</property>
                <property name="title">Italic text</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;z</property>
                <property name="title">Undo</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;y</property>
                <property name="title">Redo</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;plus</property>
                <property name="title">Zoom in / Increase font</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;minus</property>
                <property name="title">Zoom out / Decrease font</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;0</property>
                <property name="title">Reset font size</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">Tab</property>
                <property name="title">Next table cell or indent</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>
"""
        builder.add_from_string(shortcuts_xml)
        shortcuts_win = builder.get_object("shortcuts_window")
        shortcuts_win.set_transient_for(parent)
        shortcuts_win.present()

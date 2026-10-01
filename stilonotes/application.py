# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from pathlib import Path
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

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        group.set_title("Appearance")
        group.set_description("Customize how Stilo Notes looks")

        theme_row = Adw.ComboRow()
        theme_row.set_title("Color Scheme")
        model = Gtk.StringList.new(["Follow System", "Light", "Dark"])
        theme_row.set_model(model)

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
        group.add(theme_row)
        page.add(group)

        # Storage group
        group_storage = Adw.PreferencesGroup()
        group_storage.set_title("Storage")
        path_row = Adw.ActionRow()
        path_row.set_title("Database Location")
        if self.db:
            path_row.set_subtitle(str(self.db.db_path))
        group_storage.add(path_row)
        page.add(group_storage)

        dialog.add(page)
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

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Tuple
from gi.repository import Gio, GLib
from stilonotes.const import APP_ID

class ConfigManager:
    """Manages application settings and session memory."""

    _instance: Optional["ConfigManager"] = None

    def __init__(self, db=None):
        self.db = db
        self.settings: Optional[Gio.Settings] = None

        # Try loading Gio.Settings if schema is installed
        try:
            source = Gio.SettingsSchemaSource.get_default()
            if source and source.lookup(APP_ID, True):
                self.settings = Gio.Settings.new(APP_ID)
        except Exception:
            self.settings = None

    @classmethod
    def get_default(cls, db=None) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = ConfigManager(db)
        elif db and cls._instance.db is None:
            cls._instance.db = db
        return cls._instance

    def get_window_size(self) -> Tuple[int, int]:
        if self.settings:
            try:
                val = self.settings.get_value("window-size")
                if val:
                    return val.unpack()
            except Exception:
                pass
        if self.db:
            raw = self.db.get_setting("window_size", "920,680")
            try:
                w, h = map(int, raw.split(","))
                return w, h
            except Exception:
                pass
        return 920, 680

    def set_window_size(self, width: int, height: int):
        if self.settings:
            try:
                self.settings.set_value("window-size", GLib.Variant("(ii)", (width, height)))
            except Exception:
                pass
        if self.db:
            self.db.set_setting("window_size", f"{width},{height}")

    def get_window_maximized(self) -> bool:
        if self.settings:
            try:
                return self.settings.get_boolean("window-maximized")
            except Exception:
                pass
        if self.db:
            return self.db.get_setting("window_maximized", "false") == "true"
        return False

    def set_window_maximized(self, maximized: bool):
        if self.settings:
            try:
                self.settings.set_boolean("window-maximized", maximized)
            except Exception:
                pass
        if self.db:
            self.db.set_setting("window_maximized", "true" if maximized else "false")

    def get_last_opened_note_id(self) -> str:
        if self.db:
            return self.db.get_setting("last_opened_note_id", "")
        return ""

    def set_last_opened_note_id(self, note_id: str):
        if self.db:
            self.db.set_setting("last_opened_note_id", note_id)

    def get_last_category(self) -> str:
        if self.db:
            return self.db.get_setting("last_category", "all")
        return "all"

    def set_last_category(self, cat: str):
        if self.db:
            self.db.set_setting("last_category", cat)

    def get_theme_mode(self) -> str:
        """Return 'system', 'light', or 'dark'."""
        if self.db:
            return self.db.get_setting("theme_mode", "system")
        return "system"

    def set_theme_mode(self, mode: str):
        if self.db:
            self.db.set_setting("theme_mode", mode)

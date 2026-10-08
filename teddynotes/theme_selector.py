# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Callable
from gi.repository import Adw, Gtk, GObject
from teddynotes.config_manager import ConfigManager


class ThemeSelector(Gtk.Box):
    """Circular 3-option theme selector (Follow System, Light, Dark) matching Iotas."""

    __gtype_name__ = "ThemeSelector"

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_theme_changed: Optional[Callable[[bool], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.add_css_class("themeselector")
        self.set_hexpand(True)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(9)
        self.set_margin_end(9)

        self.config_manager = config_manager or ConfigManager.get_default()
        self.on_theme_changed = on_theme_changed
        self._updating = False

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner_box.set_hexpand(True)
        self.append(inner_box)

        # 1. Follow System Style button
        self._follow = Gtk.CheckButton()
        self._follow.set_tooltip_text("Follow System Style")
        self._follow.set_hexpand(True)
        self._follow.set_halign(Gtk.Align.CENTER)
        self._follow.set_focus_on_click(False)
        self._follow.add_css_class("theme-selector")
        self._follow.add_css_class("follow")
        inner_box.append(self._follow)

        # 2. Light Style button
        self._light = Gtk.CheckButton()
        self._light.set_tooltip_text("Light Style")
        self._light.set_group(self._follow)
        self._light.set_hexpand(True)
        self._light.set_halign(Gtk.Align.CENTER)
        self._light.set_focus_on_click(False)
        self._light.add_css_class("theme-selector")
        self._light.add_css_class("light")
        inner_box.append(self._light)

        # 3. Dark Style button
        self._dark = Gtk.CheckButton()
        self._dark.set_tooltip_text("Dark Style")
        self._dark.set_group(self._follow)
        self._dark.set_hexpand(True)
        self._dark.set_halign(Gtk.Align.CENTER)
        self._dark.set_focus_on_click(False)
        self._dark.add_css_class("theme-selector")
        self._dark.add_css_class("dark")
        inner_box.append(self._dark)

        self._follow.connect("toggled", self._on_option_selected)
        self._light.connect("toggled", self._on_option_selected)
        self._dark.connect("toggled", self._on_option_selected)

        self.populate()

    def _on_option_selected(self, _widget: Gtk.CheckButton):
        if self._updating:
            return
        name = None
        if self._follow.get_active():
            name = "follow"
        elif self._light.get_active():
            name = "light"
        elif self._dark.get_active():
            name = "dark"

        if name:
            self.config_manager.set_theme_mode(name)
            self._apply_style(name)

    def _apply_style(self, style: str):
        manager = Adw.StyleManager.get_default()
        if style == "dark":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif style == "light":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        if self.on_theme_changed:
            self.on_theme_changed(manager.get_dark())

    def populate(self):
        self._updating = True
        mode = self.config_manager.get_theme_mode()
        if mode == "light":
            self._light.set_active(True)
        elif mode == "dark":
            self._dark.set_active(True)
        else:
            self._follow.set_active(True)
        self._updating = False

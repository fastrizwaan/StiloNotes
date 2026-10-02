# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Callable
from gi.repository import Gtk, GObject
from stilonotes.config_manager import ConfigManager


class FontSizeSelector(Gtk.Box):
    """Note zoom / text size selector with [-] {percent}% [+] in 10% steps (80%..160%)."""

    __gtype_name__ = "FontSizeSelector"

    VALID_PERCENTAGES = [80, 90, 100, 110, 120, 130, 140, 150, 160]

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_font_size_changed: Optional[Callable[[int], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_hexpand(True)
        self.set_margin_top(4)
        self.set_margin_bottom(6)
        self.set_margin_start(18)
        self.set_margin_end(18)

        self.config_manager = config_manager or ConfigManager.get_default()
        self.on_font_size_changed = on_font_size_changed

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner_box.set_hexpand(True)
        self.append(inner_box)

        # Decrease button [-]
        self._decrease_btn = Gtk.Button()
        self._decrease_btn.set_icon_name("list-remove-symbolic")
        self._decrease_btn.set_tooltip_text("Zoom Out")
        self._decrease_btn.set_focus_on_click(False)
        self._decrease_btn.add_css_class("circular")
        self._decrease_btn.connect("clicked", lambda _b: self.decrease())
        inner_box.append(self._decrease_btn)

        # Label [ 100% ]
        self._label = Gtk.Label()
        self._label.set_hexpand(True)
        self._label.set_halign(Gtk.Align.CENTER)
        inner_box.append(self._label)

        # Increase button [+]
        self._increase_btn = Gtk.Button()
        self._increase_btn.set_icon_name("list-add-symbolic")
        self._increase_btn.set_tooltip_text("Zoom In")
        self._increase_btn.set_focus_on_click(False)
        self._increase_btn.add_css_class("circular")
        self._increase_btn.connect("clicked", lambda _b: self.increase())
        inner_box.append(self._increase_btn)

        self.refresh()

    def get_current_size(self) -> int:
        return self.get_current_percent()

    def get_current_percent(self) -> int:
        return self.config_manager.get_editor_zoom_percent()

    def set_percent(self, percent: int):
        self.config_manager.set_editor_zoom_percent(percent)
        self.refresh()
        if self.on_font_size_changed:
            self.on_font_size_changed(percent)

    def set_size(self, size: int):
        self.set_percent(size)

    def increase(self):
        curr = self.get_current_percent()
        if curr in self.VALID_PERCENTAGES:
            idx = self.VALID_PERCENTAGES.index(curr)
            if idx + 1 < len(self.VALID_PERCENTAGES):
                self.set_percent(self.VALID_PERCENTAGES[idx + 1])
        else:
            greater = [s for s in self.VALID_PERCENTAGES if s > curr]
            if greater:
                self.set_percent(greater[0])

    def decrease(self):
        curr = self.get_current_percent()
        if curr in self.VALID_PERCENTAGES:
            idx = self.VALID_PERCENTAGES.index(curr)
            if idx - 1 >= 0:
                self.set_percent(self.VALID_PERCENTAGES[idx - 1])
        else:
            smaller = [s for s in self.VALID_PERCENTAGES if s < curr]
            if smaller:
                self.set_percent(smaller[-1])

    def reset(self):
        self.set_percent(100)

    def refresh(self):
        percent = self.get_current_percent()
        self._label.set_label(f"{percent}%")
        if percent in self.VALID_PERCENTAGES:
            idx = self.VALID_PERCENTAGES.index(percent)
            self._increase_btn.set_sensitive(idx + 1 < len(self.VALID_PERCENTAGES))
            self._decrease_btn.set_sensitive(idx - 1 >= 0)
        else:
            self._increase_btn.set_sensitive(percent < 160)
            self._decrease_btn.set_sensitive(percent > 80)

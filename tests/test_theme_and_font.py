# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.editor_html import get_editor_html_page
from stilonotes.font_size_selector import FontSizeSelector


class TestThemeAndFont(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_theme_mode_default_and_persistence(self):
        self.assertEqual(self.config.get_theme_mode(), "follow")

        self.config.set_theme_mode("dark")
        self.assertEqual(self.config.get_theme_mode(), "dark")

        self.config.set_theme_mode("light")
        self.assertEqual(self.config.get_theme_mode(), "light")

        # system alias maps to follow
        self.config.set_theme_mode("system")
        self.assertEqual(self.config.get_theme_mode(), "follow")

    def test_font_size_default_and_persistence(self):
        self.assertEqual(self.config.get_font_size(), 16)

        self.config.set_font_size(20)
        self.assertEqual(self.config.get_font_size(), 20)

        self.config.set_font_size(12)
        self.assertEqual(self.config.get_font_size(), 12)

    def test_view_mode_default_and_persistence(self):
        self.assertEqual(self.config.get_view_mode(), "list")

        self.config.set_view_mode("grid")
        self.assertEqual(self.config.get_view_mode(), "grid")

        self.config.set_view_mode("list")
        self.assertEqual(self.config.get_view_mode(), "list")

        # invalid fallback
        self.config.set_view_mode("invalid")
        self.assertEqual(self.config.get_view_mode(), "list")

    def test_font_size_selector_stepping(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        selector = FontSizeSelector(self.config)
        self.assertEqual(selector.get_current_size(), 16)

        selector.increase()
        self.assertEqual(selector.get_current_size(), 17)

        selector.increase()
        self.assertEqual(selector.get_current_size(), 18)

        selector.decrease()
        self.assertEqual(selector.get_current_size(), 17)

        selector.reset()
        self.assertEqual(selector.get_current_size(), 16)

    def test_get_editor_html_page_theme_and_font_size(self):
        html_light = get_editor_html_page("<p>Hello</p>", is_dark=False, font_size=16)
        self.assertIn('class="light-theme"', html_light)
        self.assertIn('--base-font-size: 16pt;', html_light)
        self.assertIn('<p>Hello</p>', html_light)

        html_dark = get_editor_html_page("<p>World</p>", is_dark=True, font_size=22)
        self.assertIn('class="dark-theme"', html_dark)
        self.assertIn('--base-font-size: 22pt;', html_dark)
        self.assertIn('<p>World</p>', html_dark)


if __name__ == "__main__":
    unittest.main()

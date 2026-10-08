# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from teddynotes.database import NoteDatabase
from teddynotes.config_manager import ConfigManager
from teddynotes.models import Note
from teddynotes.page_setup import (
    create_default_page_setup,
    to_points,
    from_points,
    PAPER_NAMES,
    FACTORS,
    show_page_setup_dialog,
)
from teddynotes.exporter import render_printable_html, Printer


class TestPageSetup(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def test_default_page_setup(self):
        ps = create_default_page_setup()
        self.assertIsNotNone(ps)
        paper = ps.get_paper_size()
        self.assertEqual(paper.get_name(), Gtk.PAPER_NAME_A4)
        self.assertEqual(ps.get_orientation(), Gtk.PageOrientation.PORTRAIT)
        self.assertAlmostEqual(ps.get_top_margin(Gtk.Unit.POINTS), 72.0)
        self.assertAlmostEqual(ps.get_right_margin(Gtk.Unit.POINTS), 72.0)
        self.assertAlmostEqual(ps.get_bottom_margin(Gtk.Unit.POINTS), 72.0)
        self.assertAlmostEqual(ps.get_left_margin(Gtk.Unit.POINTS), 72.0)

    def test_unit_conversions(self):
        # 1 inch = 72 points
        self.assertAlmostEqual(to_points(1.0, "in"), 72.0)
        self.assertAlmostEqual(from_points(72.0, "in"), 1.0)

        # 25.4 mm = 72 points
        self.assertAlmostEqual(to_points(25.4, "mm"), 72.0, places=3)
        self.assertAlmostEqual(from_points(72.0, "mm"), 25.4, places=3)

        # 2.54 cm = 72 points
        self.assertAlmostEqual(to_points(2.54, "cm"), 72.0, places=3)
        self.assertAlmostEqual(from_points(72.0, "cm"), 2.54, places=3)

        # points to points
        self.assertAlmostEqual(to_points(50.0, "pt"), 50.0)
        self.assertAlmostEqual(from_points(50.0, "pt"), 50.0)

    def test_config_manager_page_setup_persistence(self):
        ps = Gtk.PageSetup.new()
        ps.set_paper_size(Gtk.PaperSize.new(Gtk.PAPER_NAME_LETTER))
        ps.set_orientation(Gtk.PageOrientation.LANDSCAPE)
        ps.set_top_margin(36.0, Gtk.Unit.POINTS)
        ps.set_right_margin(40.0, Gtk.Unit.POINTS)
        ps.set_bottom_margin(50.0, Gtk.Unit.POINTS)
        ps.set_left_margin(60.0, Gtk.Unit.POINTS)

        self.config.set_page_setup(ps, unit="mm")

        self.assertEqual(self.config.get_page_setup_paper(), "na_letter")
        self.assertEqual(self.config.get_page_setup_orientation(), "landscape")
        self.assertEqual(self.config.get_page_setup_unit(), "mm")
        margins = self.config.get_page_setup_margins_points()
        self.assertAlmostEqual(margins[0], 36.0, places=1)
        self.assertAlmostEqual(margins[1], 40.0, places=1)
        self.assertAlmostEqual(margins[2], 50.0, places=1)
        self.assertAlmostEqual(margins[3], 60.0, places=1)

        loaded_ps = self.config.get_page_setup()
        self.assertEqual(loaded_ps.get_paper_size().get_name(), Gtk.PAPER_NAME_LETTER)
        self.assertEqual(loaded_ps.get_orientation(), Gtk.PageOrientation.LANDSCAPE)
        self.assertAlmostEqual(loaded_ps.get_top_margin(Gtk.Unit.POINTS), 36.0, places=1)

    def test_render_printable_html_with_page_setup(self):
        note = Note(title="Meeting Notes", content_markdown="Discussion on roadmap")
        ps = Gtk.PageSetup.new()
        ps.set_paper_size(Gtk.PaperSize.new(Gtk.PAPER_NAME_A4))
        ps.set_orientation(Gtk.PageOrientation.LANDSCAPE)
        ps.set_top_margin(50.0, Gtk.Unit.POINTS)
        ps.set_right_margin(60.0, Gtk.Unit.POINTS)
        ps.set_bottom_margin(70.0, Gtk.Unit.POINTS)
        ps.set_left_margin(80.0, Gtk.Unit.POINTS)

        html_out = render_printable_html(note, db=self.db, page_setup=ps)
        self.assertIn("@page", html_out)
        self.assertIn("landscape", html_out)
        self.assertIn("50.0pt 60.0pt 70.0pt 80.0pt", html_out)


if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.models import Note
from stilonotes.selection_header_bar import SelectionHeaderBar


class TestSelectionHeaderBar(unittest.TestCase):
    def setUp(self):
        self.bar = SelectionHeaderBar()
        self.note1 = Note(id="1", title="First Note", content_html="", content_markdown="", category="Personal")
        self.note2 = Note(id="2", title="Second Note", content_html="", content_markdown="", category="Work")

    def test_initial_state(self):
        self.bar.activate()
        self.assertEqual(len(self.bar.get_selected_notes()), 0)
        self.assertEqual(self.bar._count_label.get_text(), "0 Selected")
        self.assertFalse(self.bar.delete_btn.get_sensitive())
        self.assertFalse(self.bar.category_btn.get_sensitive())

    def test_selected_notes_update(self):
        self.bar.set_selected_notes([self.note1, self.note2])
        self.assertEqual(len(self.bar.get_selected_notes()), 2)
        self.assertEqual(self.bar._count_label.get_text(), "2 Selected")
        self.assertTrue(self.bar.delete_btn.get_sensitive())
        self.assertTrue(self.bar.favorite_btn.get_sensitive())
        self.assertTrue(self.bar.export_btn.get_sensitive())
        self.assertTrue(self.bar.category_btn.get_sensitive())

    def test_signals(self):
        self.bar.set_selected_notes([self.note1])

        events = []
        self.bar.connect("set-favourite", lambda _b: events.append("fav"))
        self.bar.connect("export", lambda _b: events.append("export"))
        self.bar.connect("delete", lambda _b: events.append("delete"))
        self.bar.connect("abort", lambda _b: events.append("abort"))
        self.bar.connect("select-all", lambda _b: events.append("select-all"))

        self.bar.favorite_btn.emit("clicked")
        self.bar.export_btn.emit("clicked")
        self.bar.delete_btn.emit("clicked")
        self.bar.back_btn.emit("clicked")
        self.bar.select_all_btn.emit("clicked")

        self.assertEqual(events, ["fav", "export", "delete", "abort", "select-all"])

    def test_category_flow(self):
        self.bar.set_selected_notes([self.note1])
        self.bar.set_categories_model(["Personal", "Work", "Ideas"])
        self.bar.edit_category_for_selection()

        self.assertEqual(self.bar._stack.get_visible_child_name(), "category")
        self.assertEqual(self.bar._category_header_bar.entry.get_text(), "Personal")

        cats = []
        self.bar.connect("categories-changed", lambda _b, cat: cats.append(cat))
        self.bar._category_header_bar._on_apply()

        self.assertEqual(cats, ["Personal"])
        self.assertEqual(self.bar._stack.get_visible_child_name(), "main")


if __name__ == "__main__":
    unittest.main()

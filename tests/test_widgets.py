# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase


class TestDatabaseCountsAndFilter(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")

    def tearDown(self):
        self.db.close()

    def test_counts(self):
        counts = self.db.get_counts()
        self.assertIn("all", counts)
        self.assertIn("pinned", counts)
        self.assertIn("todo", counts)
        self.assertIn("uncategorized", counts)
        self.assertIn("trash", counts)
        self.assertGreaterEqual(counts["all"], 1)

    def test_uncategorized_filter(self):
        notes = self.db.get_notes(filter_type="uncategorized")
        self.assertIsInstance(notes, list)

    def test_create_and_delete_category(self):
        self.assertTrue(self.db.create_category("TestCategory"))
        categories = self.db.get_categories()
        names = [c.name for c in categories]
        self.assertIn("TestCategory", names)

        self.db.delete_category("TestCategory")
        categories_after = self.db.get_categories()
        names_after = [c.name for c in categories_after]
        self.assertNotIn("TestCategory", names_after)

    def test_insert_link_dialog(self):
        import json
        from gi.repository import Adw
        from stilonotes.editor import NoteEditor

        ed = NoteEditor(self.db)

        class FakeJsResult:
            def __init__(self, data):
                self._data = data
            def get_js_value(self):
                return self
            def to_string(self):
                return json.dumps(self._data)

        presented_dialog = []
        orig_present = Adw.AlertDialog.present
        def fake_present(dlg, parent):
            presented_dialog.append(dlg)
        Adw.AlertDialog.present = fake_present

        try:
            ed._on_js_insert_link(None, FakeJsResult({"text": "My Label", "url": "https://example.org"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg = presented_dialog[0]
            self.assertEqual(dlg.get_heading(), "Insert Link")

            # Verify extra child has the two entries
            box = dlg.get_extra_child()
            self.assertIsNotNone(box)

            def find_entry_rows(widget):
                found = []
                child = widget.get_first_child()
                while child:
                    if isinstance(child, Adw.EntryRow):
                        found.append(child)
                    found.extend(find_entry_rows(child))
                    child = child.get_next_sibling()
                return found

            rows = find_entry_rows(box)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].get_title(), "Label")
            self.assertEqual(rows[0].get_text(), "My Label")
            self.assertEqual(rows[1].get_title(), "URL")
            self.assertEqual(rows[1].get_text(), "https://example.org")
        finally:
            Adw.AlertDialog.present = orig_present


if __name__ == "__main__":
    unittest.main()

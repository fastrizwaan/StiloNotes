# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase


class TestDatabaseCountsAndFilter(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")

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


if __name__ == "__main__":
    unittest.main()

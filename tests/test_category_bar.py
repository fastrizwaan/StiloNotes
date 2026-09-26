# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase
from stilonotes.category_header_bar import CategoryHeaderBar


class TestCategoryHeaderBar(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.bar = CategoryHeaderBar()

    def test_set_categories_and_apply(self):
        self.bar.set_categories(["friend", "music", "work"])
        self.bar.entry.set_text("music")

        applied = []
        self.bar.connect("category-changed", lambda _b, cat: applied.append(cat))
        self.bar._on_apply()

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0], "music")

    def test_clear_category(self):
        self.bar.entry.set_text("friend")

        applied = []
        self.bar.connect("category-changed", lambda _b, cat: applied.append(cat))
        self.bar._on_clear()

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0], "")


if __name__ == "__main__":
    unittest.main()

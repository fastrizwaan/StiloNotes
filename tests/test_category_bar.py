# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase
from stilonotes.category_header_bar import CategoryHeaderBar


class TestCategoryHeaderBar(unittest.TestCase):
    def setUp(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        self.db = NoteDatabase(":memory:")
        self.bar = CategoryHeaderBar()

    def tearDown(self):
        self.db.close()

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

    def test_set_and_get_category(self):
        self.bar.set_category("Fast")
        self.assertEqual(self.bar.get_category(), "Fast")
        self.assertEqual(self.bar.entry.get_text(), "Fast")

        self.bar.set_category("")
        self.assertEqual(self.bar.get_category(), "")
        self.assertEqual(self.bar.entry.get_text(), "")

    def test_set_categories_deduplication_and_no_uncategorized(self):
        self.bar.set_categories(["Personal", "personal", "Work", "Uncategorized", "uncategorized", "Personal/Reports"])
        items = [self.bar.list_store[i][0] for i in range(len(self.bar.list_store))]
        self.assertEqual(items, ["Personal", "Personal/Reports", "Work"])
        self.assertNotIn("Uncategorized", items)
        self.assertNotIn("uncategorized", items)

    def test_apply_uncategorized_emits_empty(self):
        self.bar.entry.set_text("Uncategorized")
        applied = []
        self.bar.connect("category-changed", lambda _b, cat: applied.append(cat))
        self.bar._on_apply()
        self.assertEqual(applied, [""])

    def test_set_uncategorized_category_clears_entry(self):
        self.bar.set_category("Uncategorized")
        self.assertEqual(self.bar.entry.get_text(), "")
        self.assertEqual(self.bar.get_category(), "")

    def test_inbuilt_clear_icon(self):
        from gi.repository import Gtk
        self.bar.set_category("Personal")
        self.assertEqual(self.bar.entry.get_text(), "Personal")
        self.assertEqual(self.bar.entry.get_icon_name(Gtk.EntryIconPosition.SECONDARY), "edit-clear-symbolic")

        # Simulate clicking the secondary clear icon inside entry
        self.bar._on_icon_released(self.bar.entry, Gtk.EntryIconPosition.SECONDARY)
        self.assertEqual(self.bar.entry.get_text(), "")
        self.assertIsNone(self.bar.entry.get_icon_name(Gtk.EntryIconPosition.SECONDARY))

    def test_suggestions_popover_structure_no_dropdown_button(self):
        from gi.repository import Gtk
        self.assertFalse(hasattr(self.bar, "dropdown_btn"))
        self.assertIsInstance(self.bar.suggestions_popover, Gtk.Popover)
        self.assertEqual(self.bar.suggestions_popover.get_parent(), self.bar.entry)

    def test_suggestions_lists_all_when_text_selected(self):
        self.bar.set_categories(["Alpha", "Beta", "Gamma"])
        self.bar.set_category("Alpha")
        # Text is selected
        self.bar.entry.select_region(0, -1)
        self.bar._populate_suggestions(show_all=True)

        rows = []
        child = self.bar.categories_listbox.get_first_child()
        while child:
            rows.append(child)
            child = child.get_next_sibling()

        # Should list No Category, separator, Alpha, Beta, Gamma
        self.assertGreaterEqual(len(rows), 4)
        cat_values = [getattr(r, "_category_value", None) for r in rows if hasattr(r, "_category_value")]
        self.assertIn("", cat_values)
        self.assertIn("Alpha", cat_values)
        self.assertIn("Beta", cat_values)
        self.assertIn("Gamma", cat_values)

    def test_suggestions_filters_when_typing(self):
        self.bar.set_categories(["Alpha", "Beta", "Gamma"])
        self.bar._populate_suggestions(filter_text="Bet", show_all=False)

        rows = []
        child = self.bar.categories_listbox.get_first_child()
        while child:
            if hasattr(child, "_category_value"):
                rows.append(child._category_value)
            child = child.get_next_sibling()

        self.assertIn("Beta", rows)
        self.assertNotIn("Alpha", rows)
        self.assertNotIn("Gamma", rows)

    def test_direct_selection_applies_category(self):
        self.bar.set_categories(["Alpha", "Beta", "Gamma"])
        self.bar._populate_suggestions(show_all=True)

        rows = []
        child = self.bar.categories_listbox.get_first_child()
        while child:
            rows.append(child)
            child = child.get_next_sibling()

        applied = []
        self.bar.connect("category-changed", lambda _b, cat: applied.append(cat))

        # Find row for Beta
        beta_row = next(r for r in rows if getattr(r, "_category_value", None) == "Beta")
        self.bar._on_category_row_activated(self.bar.categories_listbox, beta_row)
        self.assertEqual(self.bar.entry.get_text(), "Beta")
        self.assertEqual(applied, ["Beta"])

        # Find row for No Category
        none_row = next(r for r in rows if getattr(r, "_category_value", None) == "")
        self.bar._on_category_row_activated(self.bar.categories_listbox, none_row)
        self.assertEqual(self.bar.entry.get_text(), "")
        self.assertEqual(applied, ["Beta", ""])

    def test_popover_width_matches_entry(self):
        self.bar.entry.set_size_request(380, -1)
        self.bar._update_popover_width()
        self.assertTrue(hasattr(self.bar, "pop_box"))
        self.assertGreaterEqual(self.bar.pop_box.get_size_request()[0], 260)


if __name__ == "__main__":
    unittest.main()

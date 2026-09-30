# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase
from stilonotes.config_manager import ConfigManager
from stilonotes.models import Category
from stilonotes.sidebar import _build_category_tree


class TestSidebarTreeAndCollapse(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_build_category_tree_flat(self):
        cats = [Category(id="1", name="Work"), Category(id="2", name="Personal")]
        tree = _build_category_tree(cats)
        # Should be sorted: Personal, Work
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0], ("Personal", 0, "Personal", False))
        self.assertEqual(tree[1], ("Work", 0, "Work", False))

    def test_build_category_tree_nested(self):
        cats = [
            Category(id="1", name="Personal"),
            Category(id="2", name="Personal/Due"),
            Category(id="3", name="Personal/Due/Urgent"),
            Category(id="4", name="Work"),
        ]
        tree = _build_category_tree(cats)
        self.assertEqual(len(tree), 4)

        # 1. Personal (depth 0, has_children=True)
        self.assertEqual(tree[0], ("Personal", 0, "Personal", True))
        # 2. Personal/Due (depth 1, has_children=True)
        self.assertEqual(tree[1], ("Personal/Due", 1, "Due", True))
        # 3. Personal/Due/Urgent (depth 2, has_children=False)
        self.assertEqual(tree[2], ("Personal/Due/Urgent", 2, "Urgent", False))
        # 4. Work (depth 0, has_children=False)
        self.assertEqual(tree[3], ("Work", 0, "Work", False))

    def test_build_category_tree_implicit_parent(self):
        # Category where parent was not separately created in db
        cats = [Category(id="1", name="Projects/Alpha/Tasks")]
        tree = _build_category_tree(cats)
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0], ("Projects", 0, "Projects", True))
        self.assertEqual(tree[1], ("Projects/Alpha", 1, "Alpha", True))
        self.assertEqual(tree[2], ("Projects/Alpha/Tasks", 2, "Tasks", False))

    def test_category_visibility_logic(self):
        # Simulate _is_category_visible logic
        def is_visible(collapsed: set, cat_name: str) -> bool:
            parts = cat_name.split("/")
            for i in range(1, len(parts)):
                if "/".join(parts[:i]) in collapsed:
                    return False
            return True

        collapsed = set()
        self.assertTrue(is_visible(collapsed, "Personal"))
        self.assertTrue(is_visible(collapsed, "Personal/Due"))
        self.assertTrue(is_visible(collapsed, "Personal/Due/Urgent"))

        # Collapse root: Personal
        collapsed.add("Personal")
        self.assertTrue(is_visible(collapsed, "Personal"))  # Root itself is visible
        self.assertFalse(is_visible(collapsed, "Personal/Due"))
        self.assertFalse(is_visible(collapsed, "Personal/Due/Urgent"))
        self.assertTrue(is_visible(collapsed, "Work"))

        # Uncollapse Personal, collapse Personal/Due
        collapsed.remove("Personal")
        collapsed.add("Personal/Due")
        self.assertTrue(is_visible(collapsed, "Personal"))
        self.assertTrue(is_visible(collapsed, "Personal/Due"))  # Due itself is visible
        self.assertFalse(is_visible(collapsed, "Personal/Due/Urgent"))  # Children hidden

    def test_config_manager_collapsed_persistence(self):
        self.assertEqual(self.config.get_collapsed_categories(), set())

        self.config.set_collapsed_categories({"Personal", "Work/Projects"})
        loaded = self.config.get_collapsed_categories()
        self.assertEqual(loaded, {"Personal", "Work/Projects"})

        self.config.set_collapsed_categories(set())
        self.assertEqual(self.config.get_collapsed_categories(), set())


if __name__ == "__main__":
    unittest.main()

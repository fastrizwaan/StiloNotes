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


    def test_sidebar_title_and_order(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from stilonotes.sidebar import Sidebar
        sidebar = Sidebar(self.db)
        self.assertEqual(sidebar.window_title.get_title(), "Stilo Notes")

        # Inspect rows
        rows = []
        for i in range(10):
            r = sidebar.listbox.get_row_at_index(i)
            if not r:
                break
            filter_type = getattr(r, "_filter_type", None)
            if filter_type:
                rows.append(filter_type)

        # Expected order: all, favorites, todos, lists, recent, uncategorized
        self.assertEqual(rows[:6], ["all", "favorites", "todos", "lists", "recent", "uncategorized"])

    def test_todo_filtering_with_brackets(self):
        # Clean db notes
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.commit()

        # Note 1: has [ ] checklist
        self.db.create_note(title="Todo Note", initial_text="Shopping:\n[ ] Buy apples\n[ ] Buy milk")
        # Note 2: has - [x] checklist
        self.db.create_note(title="Done Note", initial_text="Task:\n- [x] Finished item")
        # Note 3: regular note
        self.db.create_note(title="Regular Note", initial_text="Just a note without checkboxes")

        counts = self.db.get_counts()
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["todos"], 2)

        todo_notes = self.db.get_notes(filter_type="todos")
        self.assertEqual(len(todo_notes), 2)
        titles = {n.title for n in todo_notes}
        self.assertEqual(titles, {"Todo Note", "Done Note"})

    def test_lists_filtering_with_bullet_and_number(self):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.commit()

        # Note 1: bullet list with *
        self.db.create_note(title="Star List", initial_text="* Item 1\n* Item 2")
        # Note 2: numbered list with 1.
        self.db.create_note(title="Numbered List", initial_text="1. First\n2. Second")
        # Note 3: bullet list with -
        self.db.create_note(title="Dash List", initial_text="- Point A\n- Point B")
        # Note 4: checklist only (should NOT count as bullet list)
        self.db.create_note(title="Only Checklist", initial_text="- [ ] Task A\n- [ ] Task B")
        # Note 5: plain note
        self.db.create_note(title="Plain", initial_text="Simple text without lists")

        counts = self.db.get_counts()
        self.assertEqual(counts["all"], 5)
        self.assertEqual(counts["lists"], 3)

        list_notes = self.db.get_notes(filter_type="lists")
        self.assertEqual(len(list_notes), 3)
        titles = {n.title for n in list_notes}
        self.assertEqual(titles, {"Star List", "Numbered List", "Dash List"})

    def test_category_and_subcategory_note_counts(self):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.execute("DELETE FROM categories")
            conn.commit()

        # Create category hierarchy: C, C/sd, C/Computer Networks, C/Personal, C/Work
        self.db.create_category("C")
        self.db.create_category("C/sd")
        self.db.create_category("C/Computer Networks")
        self.db.create_category("C/Personal")
        self.db.create_category("C/Work")

        # 1 note in C
        self.db.create_note(title="C Root Note", category="C")
        # 2 notes in C/sd
        self.db.create_note(title="SD Note 1", category="C/sd")
        self.db.create_note(title="SD Note 2", category="C/sd")
        # 1 note in C/Personal
        self.db.create_note(title="Personal Note 1", category="C/Personal")
        # 0 notes in C/Computer Networks
        # 0 notes in C/Work

        counts = self.db.get_counts()

        # C has 1 direct note + 2 in C/sd + 1 in C/Personal = 4 notes.
        # Subcategories themselves (4 subcategories) must NOT be counted as notes!
        self.assertEqual(counts.get("cat:C", 0), 4)
        self.assertEqual(counts.get("cat:C/sd", 0), 2)
        self.assertEqual(counts.get("cat:C/Personal", 0), 1)
        self.assertEqual(counts.get("cat:C/Computer Networks", 0), 0)
        self.assertEqual(counts.get("cat:C/Work", 0), 0)

        # In get_categories() as well
        cats = {c.name: c.count for c in self.db.get_categories()}
        self.assertEqual(cats["C"], 4)
        self.assertEqual(cats["C/sd"], 2)
        self.assertEqual(cats["C/Personal"], 1)
        self.assertEqual(cats["C/Computer Networks"], 0)
        self.assertEqual(cats["C/Work"], 0)

        # When filtering by category "C", exactly 4 notes returned
        c_notes = self.db.get_notes(filter_type="category", category_name="C")
        self.assertEqual(len(c_notes), 4)

    def test_rename_subcategory_preserves_path_and_leaf_name(self):
        # Category: Personal/Work/Projects
        old_name = "Personal/Work/Projects"
        display_name = old_name.split("/")[-1]
        self.assertEqual(display_name, "Projects")

        # When renamed to new leaf "Tasks"
        new_leaf = "Tasks"
        if "/" in old_name:
            parent_path = old_name.rsplit("/", 1)[0]
            new_name = f"{parent_path}/{new_leaf}"
        else:
            new_name = new_leaf

        self.assertEqual(new_name, "Personal/Work/Tasks")

        # Test with DB operations
        self.db.create_category("Personal")
        self.db.create_category("Personal/Work")
        self.db.create_category(old_name)
        note = self.db.create_note(title="Project Note", category=old_name)

        self.db.rename_category(old_name, new_name)
        updated_note = self.db.get_note(note.id)
        self.assertEqual(updated_note.category, "Personal/Work/Tasks")

        # Test top-level category rename
        top_old = "Personal"
        top_display = top_old.split("/")[-1]
        self.assertEqual(top_display, "Personal")
        top_new_leaf = "Life"
        if "/" in top_old:
            parent_path = top_old.rsplit("/", 1)[0]
            top_new = f"{parent_path}/{top_new_leaf}"
        else:
            top_new = top_new_leaf
        self.assertEqual(top_new, "Life")

        self.db.rename_category(top_old, top_new)
        updated_note = self.db.get_note(note.id)
        self.assertEqual(updated_note.category, "Life/Work/Tasks")


class TestToolbarPin(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_toolbar_pinned_config(self):
        self.assertFalse(self.config.get_toolbar_pinned())
        self.config.set_toolbar_pinned(True)
        self.assertTrue(self.config.get_toolbar_pinned())
        self.config.set_toolbar_pinned(False)
        self.assertFalse(self.config.get_toolbar_pinned())

    def test_formatting_bar_no_pin_button(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gdk, Gtk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from stilonotes.editor import FormattingBar
        bar = FormattingBar(exec_fn=lambda c: None)
        self.assertFalse(hasattr(bar, "pin_btn"))


if __name__ == "__main__":
    unittest.main()


# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import tempfile
import unittest
from stilonotes.database import NoteDatabase

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_stilo.db")
        self.db = NoteDatabase(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_initial_welcome_note(self):
        notes = self.db.get_notes()
        self.assertGreater(len(notes), 0)
        self.assertIn("Welcome to Stilo Notes", notes[0].title)

    def test_crud_note(self):
        # Create
        note = self.db.create_note(title="My Shopping List", category="Personal", initial_text="- [ ] Milk\n- [ ] Eggs")
        self.assertEqual(note.title, "My Shopping List")
        self.assertTrue(note.has_todo)

        # Retrieve
        fetched = self.db.get_note(note.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "My Shopping List")

        # Update
        updated = self.db.save_note(note.id, title="Weekend Shopping")
        self.assertEqual(updated.title, "Weekend Shopping")

        # Pin
        pinned_state = self.db.toggle_pin_note(note.id)
        self.assertTrue(pinned_state)
        pinned_notes = self.db.get_notes(filter_type="pinned")
        self.assertTrue(any(n.id == note.id for n in pinned_notes))

        # Trash
        self.db.delete_note(note.id)
        active_notes = self.db.get_notes(filter_type="all")
        self.assertFalse(any(n.id == note.id for n in active_notes))

        trash_notes = self.db.get_notes(filter_type="trash")
        self.assertTrue(any(n.id == note.id for n in trash_notes))

        # Restore
        self.db.restore_note(note.id)
        active_after_restore = self.db.get_notes(filter_type="all")
        self.assertTrue(any(n.id == note.id for n in active_after_restore))

        # Permanent Delete
        self.db.delete_note(note.id, permanent=True)
        self.assertIsNone(self.db.get_note(note.id))

    def test_categories(self):
        self.assertTrue(self.db.create_category("Projects", icon="folder-symbolic"))
        cats = self.db.get_categories()
        self.assertTrue(any(c.name == "Projects" for c in cats))

        note = self.db.create_note("Project X", category="Projects")
        cats_after = self.db.get_categories()
        proj_cat = next(c for c in cats_after if c.name == "Projects")
        self.assertEqual(proj_cat.count, 1)

if __name__ == "__main__":
    unittest.main()

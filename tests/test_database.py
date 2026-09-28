# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
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
        self.db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

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

    def test_rename_category_and_subcategories(self):
        self.db.create_category("Work")
        self.db.create_category("Work/Alpha")
        note1 = self.db.create_note("Task 1", category="Work")
        note2 = self.db.create_note("Task 2", category="Work/Alpha")

        self.db.rename_category("Work", "Office")

        cats = [c.name for c in self.db.get_categories()]
        self.assertIn("Office", cats)
        self.assertIn("Office/Alpha", cats)
        self.assertNotIn("Work", cats)
        self.assertNotIn("Work/Alpha", cats)

        n1 = self.db.get_note(note1.id)
        n2 = self.db.get_note(note2.id)
        self.assertEqual(n1.category, "Office")
        self.assertEqual(n2.category, "Office/Alpha")

    def test_delete_category_and_subcategories(self):
        self.db.create_category("Hobbies")
        self.db.create_category("Hobbies/Gaming")
        note = self.db.create_note("Play Game", category="Hobbies/Gaming")

        self.db.delete_category("Hobbies")

        cats = [c.name for c in self.db.get_categories()]
        self.assertNotIn("Hobbies", cats)
        self.assertNotIn("Hobbies/Gaming", cats)

        n = self.db.get_note(note.id)
        self.assertEqual(n.category, "")

    def test_attachments(self):
        note = self.db.create_note("Test Note")
        sample_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        att_id = self.db.save_attachment(
            note_id=note.id,
            filename="diagram.png",
            mime_type="image/png",
            data=sample_png
        )
        self.assertTrue(att_id)

        att = self.db.get_attachment(att_id)
        self.assertIsNotNone(att)
        self.assertEqual(att["filename"], "diagram.png")
        self.assertEqual(att["mime_type"], "image/png")
        self.assertEqual(att["data"], sample_png)

        self.db.delete_attachment(att_id)
        self.assertIsNone(self.db.get_attachment(att_id))

    def test_get_notes_lightweight(self):
        note = self.db.create_note("Heavy Note", initial_text="Long markdown content " * 100)
        # get_note returns full content
        full_note = self.db.get_note(note.id)
        self.assertTrue(len(full_note.content_markdown) > 0)

        # get_notes returns metadata list
        notes = self.db.get_notes()
        match = next(n for n in notes if n.id == note.id)
        self.assertEqual(match.title, "Heavy Note")
        self.assertEqual(match.content_markdown, "")

    def test_settings_persistence(self):
        self.assertEqual(self.db.get_setting("toolbar_pinned", "false"), "false")
        self.db.set_setting("toolbar_pinned", "true")
        self.assertEqual(self.db.get_setting("toolbar_pinned", "false"), "true")

    def test_tags_and_symbol_mapping(self):
        # 1. Create notes with #tags and ##category
        note1 = self.db.create_note(
            "Poem Study",
            initial_text="Analyzing sonnet #important #poetry in ##English/poetry"
        )
        note2 = self.db.create_note(
            "Grammar Rules",
            initial_text="Key rules #revise #important in /English/grammar"
        )

        # Verify auto-extracted tags
        n1 = self.db.get_note(note1.id)
        self.assertIn("important", n1.tags)
        self.assertIn("poetry", n1.tags)
        self.assertEqual(n1.category, "English/poetry")

        n2 = self.db.get_note(note2.id)
        self.assertIn("important", n2.tags)
        self.assertIn("revise", n2.tags)
        self.assertEqual(n2.category, "English/grammar")

        # Verify ancestor categories auto-created
        cat_names = [c.name for c in self.db.get_categories()]
        self.assertIn("English", cat_names)
        self.assertIn("English/poetry", cat_names)
        self.assertIn("English/grammar", cat_names)

        # Verify get_all_tags
        all_tags = dict(self.db.get_all_tags())
        self.assertEqual(all_tags.get("important"), 2)
        self.assertEqual(all_tags.get("poetry"), 1)
        self.assertEqual(all_tags.get("revise"), 1)

        # Verify tag filtering
        important_notes = self.db.get_notes(filter_type="tag", tag_name="important")
        self.assertEqual(len(important_notes), 2)

        poetry_notes = self.db.get_notes(filter_type="tag", tag_name="poetry")
        self.assertEqual(len(poetry_notes), 1)
        self.assertEqual(poetry_notes[0].id, note1.id)

        # Verify find_note_by_title and get_all_note_titles
        self.assertEqual(self.db.find_note_by_title("Poem Study").id, note1.id)
        self.assertIn("Poem Study", self.db.get_all_note_titles())

if __name__ == "__main__":
    unittest.main()


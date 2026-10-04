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

    def test_no_uncategorized_in_notes_or_categories(self):
        # 1. create_category should reject "Uncategorized"
        self.assertFalse(self.db.create_category("Uncategorized"))
        self.assertFalse(self.db.create_category("uncategorized"))
        cat_names = [c.name.lower() for c in self.db.get_categories()]
        self.assertNotIn("uncategorized", cat_names)

        # 2. create_note with "Uncategorized" should normalize category to ""
        note = self.db.create_note(title="No Uncat Note", category="Uncategorized")
        self.assertEqual(note.category, "")
        fetched = self.db.get_note(note.id)
        self.assertEqual(fetched.category, "")

        # 3. save_note with "uncategorized" should normalize category to ""
        saved = self.db.save_note(note.id, category="uncategorized")
        self.assertEqual(saved.category, "")

        # 4. set_note_category with "Uncategorized" should set category to ""
        self.db.set_note_category(note.id, "Uncategorized")
        fetched = self.db.get_note(note.id)
        self.assertEqual(fetched.category, "")

        # 5. set_notes_category with "uncategorized" should set category to ""
        self.db.set_notes_category([note.id], "uncategorized")
        fetched = self.db.get_note(note.id)
        self.assertEqual(fetched.category, "")

        # Verify categories table never contains uncategorized
        cat_names_after = [c.name.lower() for c in self.db.get_categories()]
        self.assertNotIn("uncategorized", cat_names_after)

    def test_all_notes_filter_sorts_strictly_by_date(self):
        import time
        now = time.time()
        # Note 1: older (2 days ago), but pinned
        n1 = self.db.create_note(title="Pinned Older Note", initial_text="pinned")
        self.db.toggle_pin_note(n1.id)
        with self.db.get_connection() as conn:
            conn.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (now - 172800, n1.id))

        # Note 2: newer (1 hour ago), unpinned
        n2 = self.db.create_note(title="Unpinned Newer Note", initial_text="newer")
        with self.db.get_connection() as conn:
            conn.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (now - 3600, n2.id))

        # For "all" filter, notes are sorted strictly by date (n2 before n1, behaving like Recents)
        all_notes = self.db.get_notes(filter_type="all")
        note_ids_all = [n.id for n in all_notes if n.id in (n1.id, n2.id)]
        self.assertEqual(note_ids_all, [n2.id, n1.id])

        # For "favorites" filter, only pinned notes are returned
        fav_notes = self.db.get_notes(filter_type="favorites")
        note_ids_fav = [n.id for n in fav_notes if n.id in (n1.id, n2.id)]
        self.assertEqual(note_ids_fav, [n1.id])

    def test_private_note_password_encryption_and_verification(self):
        # 1. Initially no password configured
        self.assertFalse(self.db.has_private_password())
        self.assertFalse(self.db.verify_private_password("secret123"))

        # 2. Set password (stored as salted PBKDF2 hash in app_settings)
        self.db.set_private_password("MySecretPass!@#")
        self.assertTrue(self.db.has_private_password())
        self.assertTrue(self.db.verify_private_password("MySecretPass!@#"))
        self.assertFalse(self.db.verify_private_password("WrongPassword"))
        self.assertFalse(self.db.verify_private_password(""))

        # Verify salt and hash in app_settings
        salt = self.db.get_setting("private_note_password_salt")
        pwd_hash = self.db.get_setting("private_note_password_hash")
        self.assertTrue(len(salt) > 0)
        self.assertTrue(len(pwd_hash) > 0)
        self.assertNotEqual(pwd_hash, "MySecretPass!@#")  # must be hashed, never plaintext

        # 3. Clear password
        self.db.clear_private_password()
        self.assertFalse(self.db.has_private_password())
        self.assertFalse(self.db.verify_private_password("MySecretPass!@#"))

    def test_private_notes_filtering_and_isolation(self):
        # Create normal note and private locked note
        normal_note = self.db.create_note(title="Public Note", category="Work", is_locked=False)
        locked_note = self.db.create_note(title="Secret Finances", category="Finance", is_locked=True)

        # 1. "all" filter must strictly exclude locked notes
        all_notes = self.db.get_notes(filter_type="all")
        all_ids = [n.id for n in all_notes]
        self.assertIn(normal_note.id, all_ids)
        self.assertNotIn(locked_note.id, all_ids)

        # 2. "private" filter must return only locked notes
        private_notes = self.db.get_notes(filter_type="private")
        private_ids = [n.id for n in private_notes]
        self.assertIn(locked_note.id, private_ids)
        self.assertNotIn(normal_note.id, private_ids)
        self.assertTrue(private_notes[0].is_locked)

        # 3. Category filter must exclude locked notes
        cat_notes = self.db.get_notes(filter_type="category", category_name="Finance")
        cat_ids = [n.id for n in cat_notes]
        self.assertNotIn(locked_note.id, cat_ids)

        # 4. Search query must exclude locked notes
        search_res = self.db.get_notes(search_query="Secret")
        search_ids = [n.id for n in search_res]
        self.assertNotIn(locked_note.id, search_ids)

        # 5. get_counts must count locked notes under "private" and isolate from "all"
        counts = self.db.get_counts()
        self.assertEqual(counts.get("private", 0), 1)

        # 6. get_all_tags must exclude tags from locked notes
        self.db.save_note(locked_note.id, tags=["confidential", "secret"])
        self.db.save_note(normal_note.id, tags=["work", "public"])
        tags_dict = dict(self.db.get_all_tags())
        self.assertIn("work", tags_dict)
        self.assertNotIn("confidential", tags_dict)
        self.assertNotIn("secret", tags_dict)

    def test_toggle_and_set_note_locked(self):
        note = self.db.create_note(title="Toggle Lock Note", is_locked=False)
        self.assertFalse(self.db.get_note(note.id).is_locked)

        # Toggle to True
        res = self.db.toggle_lock_note(note.id)
        self.assertTrue(res)
        self.assertTrue(self.db.get_note(note.id).is_locked)

        # Toggle to False
        res = self.db.toggle_lock_note(note.id)
        self.assertFalse(res)
        self.assertFalse(self.db.get_note(note.id).is_locked)

        # Explicit set_note_locked
        self.db.set_note_locked(note.id, True)
        self.assertTrue(self.db.get_note(note.id).is_locked)

    def test_import_note_from_markdown_file_with_hashtags_and_checklist(self):
        md_file = os.path.join(self.test_dir, "sprint_tasks.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Sprint Tasks #dev #urgent\n\n- [ ] Fix bug #123\n- [x] Deploy release\n")

        imported = self.db.import_note_from_file(md_file)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.title, "Sprint Tasks")
        self.assertTrue(imported.has_todo)
        self.assertIn("dev", imported.tags)
        self.assertIn("urgent", imported.tags)
        self.assertEqual(imported.category, "Dev")

        counts = self.db.get_counts()
        self.assertGreater(counts.get("todos", 0), 0)
        self.assertGreater(counts.get("cat:Dev", 0), 0)
        self.assertGreater(counts.get("tag:dev", 0), 0)

    def test_import_note_from_txt_file_with_bullet_list(self):
        txt_file = os.path.join(self.test_dir, "grocery_list.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("Grocery List\n\n* Apples\n* Milk\n* Bread\n")

        imported = self.db.import_note_from_file(txt_file)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.title, "Grocery List")
        self.assertFalse(imported.has_todo)

        counts = self.db.get_counts()
        self.assertGreater(counts.get("lists", 0), 0)

    def test_import_note_matches_existing_category_from_hashtag(self):
        self.db.create_category("Marketing")
        md_file = os.path.join(self.test_dir, "campaign.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Fall Campaign #marketing\n\nLaunch promotion soon.\n")

        imported = self.db.import_note_from_file(md_file)
        self.assertEqual(imported.category, "Marketing")
        self.assertIn("marketing", imported.tags)


    def test_get_all_tags_include_locked(self):
        note1 = self.db.create_note(title="Public Note", tags=["public_tag"])
        note2 = self.db.create_note(title="Private Note", tags=["secret_tag"], is_locked=True)

        tags_locked_excluded = dict(self.db.get_all_tags(include_locked=False))
        self.assertIn("public_tag", tags_locked_excluded)
        self.assertNotIn("secret_tag", tags_locked_excluded)

        tags_locked_included = dict(self.db.get_all_tags(include_locked=True))
        self.assertIn("public_tag", tags_locked_included)
        self.assertIn("secret_tag", tags_locked_included)

    def test_save_note_updates_tags(self):
        note = self.db.create_note(title="Dev Note", tags=["python"])
        self.assertEqual(self.db.get_note(note.id).tags, ["python"])

        # Add my_apps tag
        updated = self.db.save_note(note.id, tags=["python", "my_apps"])
        self.assertIn("my_apps", updated.tags)
        self.assertIn("python", updated.tags)

        all_tags = dict(self.db.get_all_tags())
        self.assertIn("my_apps", all_tags)
        self.assertEqual(all_tags["my_apps"], 1)


if __name__ == "__main__":
    unittest.main()


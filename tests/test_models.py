# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from teddynotes.models import Note, Category

class TestModels(unittest.TestCase):
    def test_note_creation(self):
        note = Note(title="Test Note", content_markdown="# Test Note\nHello")
        self.assertEqual(note.title, "Test Note")
        self.assertFalse(note.is_pinned)
        self.assertFalse(note.is_trashed)
        self.assertIsNotNone(note.id)

    def test_note_dict_roundtrip(self):
        note = Note(
            title="Meeting Notes",
            category="Work",
            tags=["standup", "team"],
            is_pinned=True,
            has_todo=True
        )
        d = note.to_dict()
        self.assertEqual(d["title"], "Meeting Notes")
        self.assertEqual(d["category"], "Work")
        self.assertIn("standup", d["tags"])
        self.assertTrue(d["is_pinned"])
        self.assertTrue(d["has_todo"])

    def test_version_consistency(self):
        import inspect
        import teddynotes
        from teddynotes.const import VERSION
        from teddynotes.main import main
        self.assertEqual(teddynotes.__version__, "1.3")
        self.assertEqual(VERSION, "1.3")
        sig = inspect.signature(main)
        self.assertEqual(sig.parameters["version"].default, "1.3")

if __name__ == "__main__":
    unittest.main()

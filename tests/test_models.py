# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.models import Note, Category

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

if __name__ == "__main__":
    unittest.main()

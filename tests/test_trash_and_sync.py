# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
import tempfile
import time

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib

from stilonotes.database import NoteDatabase
from stilonotes.notes_list import NotesList


class TestTrashAndSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = NoteDatabase(str(self.db_path))

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_empty_trash_permanently_deletes_only_trashed_notes_and_attachments(self):
        # 1. Create active note and trashed notes
        active_note = self.db.create_note(title="Active Note", initial_text="I am active")
        trash_note1 = self.db.create_note(title="Trash Note 1", initial_text="Trash 1")
        trash_note2 = self.db.create_note(title="Trash Note 2", initial_text="Trash 2")

        # Save attachments
        att_active = self.db.save_attachment(active_note.id, "active.png", "image/png", b"active_bytes")
        att_trash = self.db.save_attachment(trash_note1.id, "trash.png", "image/png", b"trash_bytes")

        # Trash the two notes
        self.db.delete_note(trash_note1.id, permanent=False)
        self.db.delete_note(trash_note2.id, permanent=False)

        # Confirm they are in trash
        trashed_notes = self.db.get_notes(filter_type="trash")
        self.assertEqual(len(trashed_notes), 2)

        events = []
        self.db.add_change_listener(lambda ev, data, sender: events.append((ev, data, sender)))

        # Empty trash
        deleted_count = self.db.empty_trash(sender="test_suite")
        self.assertEqual(deleted_count, 2)

        # Run GLib main loop iterations to dispatch notifications
        ctx = GLib.MainContext.default()
        while ctx.iteration(False):
            pass

        # Check notification
        self.assertTrue(any(ev == "trash-emptied" and sender == "test_suite" for ev, _, sender in events))

        # Check trash is now 0
        trashed_after = self.db.get_notes(filter_type="trash")
        self.assertEqual(len(trashed_after), 0)

        # Check active note still exists
        self.assertIsNotNone(self.db.get_note(active_note.id))
        self.assertIsNotNone(self.db.get_attachment(att_active))

        # Check trashed attachment was deleted
        self.assertIsNone(self.db.get_attachment(att_trash))

    def test_db_change_listeners_receive_events_with_sender(self):
        received = []
        def listener(ev, data, sender):
            received.append((ev, data, sender))

        self.db.add_change_listener(listener)

        note = self.db.create_note(title="Sync Note", sender="win1")
        self.db.toggle_pin_note(note.id, sender="win1")
        self.db.set_note_category(note.id, "Personal", sender="win1")
        self.db.delete_note(note.id, permanent=False, sender="win1")
        self.db.restore_note(note.id, sender="win1")

        ctx = GLib.MainContext.default()
        while ctx.iteration(False):
            pass

        event_names = [r[0] for r in received]
        self.assertIn("note-saved", event_names)
        self.assertIn("note-pin-toggled", event_names)
        self.assertIn("category-changed", event_names)
        self.assertIn("note-deleted", event_names)
        self.assertIn("note-restored", event_names)

        # All senders should match win1
        for _, _, s in received:
            self.assertEqual(s, "win1")

        self.db.remove_change_listener(listener)

    def test_notes_list_trash_empty_state(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        nl = NotesList(self.db)

        # Normal empty state
        nl.set_notes([], is_search=False, active_filter_type="all")
        self.assertEqual(nl.empty_page.get_title(), "Note List Empty")
        self.assertEqual(nl.empty_page.get_description(), "Capture your ideas, checklists, and notes in markdown.")
        self.assertEqual(nl.empty_page.get_icon_name(), "text-editor-symbolic")
        self.assertTrue(nl.empty_new_btn.get_visible())

        # Trash empty state
        nl.set_notes([], is_search=False, active_filter_type="trash")
        self.assertEqual(nl.empty_page.get_title(), "Trash is Empty")
        self.assertEqual(nl.empty_page.get_description(), "")
        self.assertEqual(nl.empty_page.get_icon_name(), "user-trash-symbolic")
        self.assertFalse(nl.empty_new_btn.get_visible())


if __name__ == "__main__":
    unittest.main()

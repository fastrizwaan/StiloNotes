# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.models import Note
from stilonotes.database import NoteDatabase
from stilonotes.notes_list import (
    NotesList,
    NoteGridCard,
    NoteListRow,
    BaseNoteCard,
    _get_note_preview
)


class TestNotesListAndCards(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")

    def tearDown(self):
        self.db.close()

    def test_get_note_preview(self):
        note = Note(
            title="My Note",
            content_markdown="# My Note\nLine 1\nLine 2\nLine 3",
            excerpt="Line 1 Line 2"
        )
        preview = _get_note_preview(note)
        self.assertEqual(preview, "Line 1\nLine 2\nLine 3")

        empty_note = Note(title="Empty", content_markdown="", excerpt="")
        self.assertEqual(_get_note_preview(empty_note), "Type text here...")

    def test_notes_list_flowbox_sections(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        notes_list = NotesList(self.db, view_mode="list")
        self.assertEqual(notes_list.view_mode, "list")

        # Verify sections use Gtk.FlowBox with homogeneous=True
        for fb in [
            notes_list.fav_flowbox,
            notes_list.today_flowbox,
            notes_list.yesterday_flowbox,
            notes_list.week_flowbox,
            notes_list.month_flowbox,
            notes_list.earlier_flowbox,
            notes_list.search_flowbox
        ]:
            self.assertTrue(fb.get_homogeneous())
            self.assertEqual(fb.get_column_spacing(), 6)
            self.assertEqual(fb.get_row_spacing(), 6)

    def test_populate_list_view_and_grid_view(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        notes_list = NotesList(self.db, view_mode="list")

        note1 = Note(title="Pinned Note", is_pinned=True, category="Work")
        note2 = Note(title="Recent Note", is_pinned=False, category="Home")
        notes = [note1, note2]

        notes_list.set_notes(notes)
        self.assertEqual(len(notes_list._all_cards), 2)
        for card in notes_list._all_cards:
            self.assertIsInstance(card, NoteListRow)

        # Switch to Grid view
        notes_list.set_view_mode("grid")
        self.assertEqual(notes_list.view_mode, "grid")
        self.assertEqual(len(notes_list._all_cards), 2)
        for card in notes_list._all_cards:
            self.assertIsInstance(card, NoteGridCard)

        # Switch back to List view
        notes_list.set_view_mode("list")
        self.assertEqual(notes_list.view_mode, "list")
        for card in notes_list._all_cards:
            self.assertIsInstance(card, NoteListRow)

    def test_selection_mode_and_checking(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        notes_list = NotesList(self.db, view_mode="grid")
        note1 = Note(title="Note 1")
        note2 = Note(title="Note 2")
        notes_list.set_notes([note1, note2])

        self.assertFalse(notes_list.selection_mode)
        notes_list.set_selection_mode(True)
        self.assertTrue(notes_list.selection_mode)

        self.assertEqual(len(notes_list.get_checked_notes()), 0)

        # Select all
        notes_list.select_all(True)
        self.assertEqual(len(notes_list.get_checked_notes()), 2)

        # Clear all
        notes_list.clear_all_checkboxes()
        self.assertEqual(len(notes_list.get_checked_notes()), 0)

    def test_image_preview_extraction(self):
        import base64
        from stilonotes.notes_list import get_note_image_bytes

        # 1. From base64 data URI
        raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        note_data_uri = Note(
            title="Image Note",
            content_markdown=f"Look at this:\n![screenshot](data:image/png;base64,{raw_b64})\nNice!"
        )
        img_bytes = get_note_image_bytes(note_data_uri, self.db)
        self.assertIsNotNone(img_bytes)
        self.assertEqual(img_bytes, base64.b64decode(raw_b64))

        # 2. From database attachment
        fake_data = b"FAKE_PNG_BINARY_DATA"
        att_id = self.db.save_attachment(
            note_id="test-note-123",
            filename="sample.png",
            mime_type="image/png",
            data=fake_data
        )
        note_att = Note(id="test-note-123", title="Attachment Note")
        img_from_db = get_note_image_bytes(note_att, self.db)
        self.assertEqual(img_from_db, fake_data)

        # 3. Note without image
        note_no_img = Note(title="Plain Text", content_markdown="Just some text.")
        self.assertIsNone(get_note_image_bytes(note_no_img, self.db))

    def test_grid_card_with_image(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        note_img = Note(
            title="Card with Image",
            content_markdown=f"![screenshot](data:image/png;base64,{raw_b64})\nDescription text"
        )
        card = NoteGridCard(note_img, db=self.db)
        self.assertIsNotNone(card.thumb)
        self.assertEqual(card.body_lbl.get_lines(), 2)


if __name__ == "__main__":
    unittest.main()


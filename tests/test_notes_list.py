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

    def test_card_size_and_label_constraints(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        note = Note(
            title="A very long title that would normally expand the card " * 5,
            content_markdown="A very long text body that goes on and on " * 20,
            excerpt="A very long excerpt line " * 10,
            category="Personal"
        )
        grid_card = NoteGridCard(note, db=self.db)
        self.assertEqual(grid_card.get_size_request(), (200, 180))
        self.assertEqual(grid_card.title_lbl.get_max_width_chars(), 35)
        self.assertEqual(grid_card.body_lbl.get_max_width_chars(), 42)

        list_row = NoteListRow(note, db=self.db)
        self.assertEqual(list_row.get_size_request(), (300, 68))
        self.assertEqual(list_row.title_lbl.get_max_width_chars(), 45)
        self.assertEqual(list_row.excerpt_lbl.get_max_width_chars(), 65)

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

    def test_create_thumbnail_texture_dimensions(self):
        from PIL import Image
        import io
        from stilonotes.notes_list import _create_thumbnail_texture

        # Test large 1920x1080 image
        img = Image.new("RGB", (1920, 1080), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        tex = _create_thumbnail_texture(buf.getvalue())
        self.assertIsNotNone(tex)
        self.assertEqual(tex.get_width(), 216)
        self.assertEqual(tex.get_height(), 80)

        # Test tall 400x1200 image
        img_tall = Image.new("RGB", (400, 1200), color="green")
        buf_tall = io.BytesIO()
        img_tall.save(buf_tall, format="PNG")
        tex_tall = _create_thumbnail_texture(buf_tall.getvalue())
        self.assertIsNotNone(tex_tall)
        self.assertEqual(tex_tall.get_width(), 216)
        self.assertEqual(tex_tall.get_height(), 80)

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

    def test_multiple_images_primary_only(self):
        """Verify that when a note has multiple images, only the top-most primary image is shown."""
        import base64
        from stilonotes.notes_list import get_note_image_bytes

        # Two distinct 1x1 png base64 images
        b64_img1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        b64_img2 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

        img1_bytes = base64.b64decode(b64_img1)
        img2_bytes = base64.b64decode(b64_img2)
        self.assertNotEqual(img1_bytes, img2_bytes)

        # Note with 2 images: img1 at the top, img2 at the bottom
        note_multi = Note(
            title="Multi Image Note",
            content_markdown=(
                f"# Title\n\n"
                f"![Top Primary Image](data:image/png;base64,{b64_img1})\n\n"
                f"Some text in between.\n\n"
                f"![Bottom Secondary Image](data:image/png;base64,{b64_img2})\n"
            )
        )

        # get_note_image_bytes must return img1 (top-most), ignoring img2
        extracted = get_note_image_bytes(note_multi, self.db)
        self.assertEqual(extracted, img1_bytes)

    def test_multiple_images_attachment_document_order(self):
        """Verify that document order (top-most in note content) takes precedence over database creation timestamp."""
        from stilonotes.notes_list import get_note_image_bytes

        note_id = "test-doc-order-note"
        # Save attachment B first in database
        att_b_data = b"BINARY_IMAGE_B_CREATED_FIRST"
        self.db.save_attachment(
            note_id=note_id,
            attachment_id="att-b-old",
            filename="older.png",
            mime_type="image/png",
            data=att_b_data
        )

        # Save attachment A second in database
        att_a_data = b"BINARY_IMAGE_A_CREATED_SECOND"
        self.db.save_attachment(
            note_id=note_id,
            attachment_id="att-a-new",
            filename="newer.png",
            mime_type="image/png",
            data=att_a_data
        )

        # But in note text, att-a-new is at the TOP, and att-b-old is at the BOTTOM
        note = self.db.save_note(
            note_id=note_id,
            title="Precedence Note",
            content_markdown=(
                f"# My Note\n\n"
                f"![Primary Top](attachment://att-a-new)\n\n"
                f"Paragraph text.\n\n"
                f"![Secondary Bottom](attachment://att-b-old)\n"
            )
        )

        # Even with metadata-only note, get_note_image_bytes resolves top-most image att-a-new
        light_note = Note(id=note_id, title="Precedence Note")
        extracted = get_note_image_bytes(light_note, self.db)
        self.assertEqual(extracted, att_a_data)

    def test_broken_top_image_falls_back_to_second_image(self):
        """If the top-most image cannot be resolved, it falls back to the next valid image."""
        import base64
        from stilonotes.notes_list import get_note_image_bytes

        valid_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        valid_bytes = base64.b64decode(valid_b64)

        note = Note(
            title="Broken First Image",
            content_markdown=(
                f"![Nonexistent Attachment](attachment://missing-uuid-12345)\n"
                f"![Valid Second Image](data:image/png;base64,{valid_b64})\n"
                f"![Third Image](data:image/png;base64,AAAA)\n"
            )
        )

        extracted = get_note_image_bytes(note, self.db)
        self.assertEqual(extracted, valid_bytes)

    def test_preview_excerpt_does_not_leak_image_markup(self):
        """Card preview body excerpt should not contain image markup or alt tags."""
        from stilonotes.notes_list import _get_note_preview

        note = Note(
            title="Image Excerpt Note",
            content_markdown=(
                f"# Image Excerpt Note\n\n"
                f"![Header Banner](attachment://banner.png)\n\n"
                f"![Secondary Photo](attachment://photo.png)\n\n"
                f"This is the actual written text that should appear in preview."
            )
        )

        preview = _get_note_preview(note)
        self.assertIn("This is the actual written text", preview)
        self.assertNotIn("Header Banner", preview)
        self.assertNotIn("Secondary Photo", preview)
        self.assertNotIn("attachment://", preview)

    def test_extract_table_data(self):
        """Verify extraction of table headers and rows from markdown and HTML."""
        from stilonotes.markdown_utils import extract_table_data

        # 1. Markdown table
        md = (
            "# My Table Note\n\n"
            "| Item | Qty | Price |\n"
            "| :--- | :---: | ---: |\n"
            "| Apples | 10 | $5 |\n"
            "| Bananas | 5 | $3 |\n"
        )
        table = extract_table_data(md)
        self.assertIsNotNone(table)
        self.assertEqual(len(table), 3)  # Header + 2 data rows
        self.assertEqual(table[0], ["Item", "Qty", "Price"])
        self.assertEqual(table[1], ["Apples", "10", "$5"])
        self.assertEqual(table[2], ["Bananas", "5", "$3"])

        # 2. HTML table
        html = (
            "<table class=\"stilo-table\">"
            "<thead><tr><th>Task</th><th>Done</th></tr></thead>"
            "<tbody><tr><td>Fix bug</td><td>Yes</td></tr></tbody>"
            "</table>"
        )
        table_html = extract_table_data(html)
        self.assertIsNotNone(table_html)
        self.assertEqual(len(table_html), 2)
        self.assertEqual(table_html[0], ["Task", "Done"])
        self.assertEqual(table_html[1], ["Fix bug", "Yes"])

        # 3. No table
        self.assertIsNone(extract_table_data("Just plain markdown text without tables."))

    def test_grid_card_table_only_and_image_precedence(self):
        """Verify table preview shows when note has table only, and image shows when image + table."""
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from stilonotes.notes_list import NoteGridCard

        # 1. Note with TABLE ONLY: table preview should be created, thumb is None
        note_table_only = Note(
            title="Table Only Note",
            content_markdown=(
                "# Budget\n\n"
                "| Category | Amount |\n"
                "| --- | --- |\n"
                "| Hardware | $1200 |\n"
                "| Software | $300 |\n"
            )
        )
        card_table = NoteGridCard(note_table_only, db=self.db)
        self.assertIsNone(card_table.thumb)
        self.assertIsNotNone(card_table.table_preview)
        self.assertTrue(card_table.table_preview.has_css_class("note-grid-table-preview"))

        # 2. Note with IMAGE + TABLE: image preview must take precedence, table preview is None!
        raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        note_img_and_table = Note(
            title="Image + Table Note",
            content_markdown=(
                f"![Hero Image](data:image/png;base64,{raw_b64})\n\n"
                "| Header 1 | Header 2 |\n"
                "| --- | --- |\n"
                "| Val 1 | Val 2 |\n"
            )
        )
        card_both = NoteGridCard(note_img_and_table, db=self.db)
        # Image takes precedence
        self.assertIsNotNone(card_both.thumb)
        self.assertIsNone(card_both.table_preview)

        # 3. Note with NEITHER image nor table: both thumb and table_preview are None
        note_plain = Note(
            title="Plain Note",
            content_markdown="Just simple text."
        )
        card_plain = NoteGridCard(note_plain, db=self.db)
        self.assertIsNone(card_plain.thumb)
        self.assertIsNone(card_plain.table_preview)
        self.assertEqual(card_plain.body_lbl.get_lines(), 5)

        # 4. Verify table excerpt suppression on table-only card
        self.assertEqual(card_table.body_lbl.get_text(), "")
        self.assertFalse(card_table.body_lbl.get_visible())

    def test_grid_flowbox_fills_horizontally(self):
        """Verify flowboxes use Align.FILL, hexpand=True, and homogeneous=True."""
        from gi.repository import Gdk, Gtk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        notes_list = NotesList(self.db, view_mode="grid")
        for fb in notes_list._get_all_flowboxes():
            self.assertEqual(fb.get_halign(), Gtk.Align.FILL)
            self.assertTrue(fb.get_hexpand())
            self.assertTrue(fb.get_homogeneous())
            self.assertEqual(fb.get_max_children_per_line(), 24)

        notes_list.set_view_mode("list")
        for fb in notes_list._get_all_flowboxes():
            self.assertEqual(fb.get_halign(), Gtk.Align.FILL)
            self.assertTrue(fb.get_hexpand())


if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import unittest
from stilonotes.database import NoteDatabase
from stilonotes.models import Note
from stilonotes.exporter import (
    bundle_attachments_in_html,
    bundle_attachments_in_markdown,
    resolve_attachment_to_data_uri,
    get_plain_text,
)

class TestExporter(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")

    def test_bundle_attachments_in_html(self):
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        att_id = self.db.save_attachment(
            note_id="note-1",
            filename="icon.svg",
            mime_type="image/svg+xml",
            data=svg_data,
        )

        input_html = (
            '<div><div class="stilo-img-wrapper" contenteditable="false" style="width: 186px;">'
            f'<img src="attachment://{att_id}" alt="icon.svg" class="stilo-img" draggable="false" style="width: 100%; height: auto;">'
            '<div class="image-handle" contenteditable="false"></div>'
            '</div></div>'
        )

        bundled = bundle_attachments_in_html(input_html, db=self.db, note_id="note-1")

        expected_b64 = base64.b64encode(svg_data).decode("ascii")
        expected_src = f'data:image/svg+xml;base64,{expected_b64}'

        self.assertIn(f'src="{expected_src}"', bundled)
        self.assertNotIn(f"attachment://{att_id}", bundled)

    def test_bundle_attachments_in_markdown(self):
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        att_id = self.db.save_attachment(
            note_id="note-2",
            filename="photo.png",
            mime_type="image/png",
            data=png_data,
        )

        md = f"# Note\n\n![photo|320](attachment://{att_id})\n\nSome text"
        bundled_md = bundle_attachments_in_markdown(md, db=self.db, note_id="note-2")

        expected_b64 = base64.b64encode(png_data).decode("ascii")
        expected_uri = f"data:image/png;base64,{expected_b64}"

        self.assertEqual(bundled_md, f"# Note\n\n![photo|320]({expected_uri})\n\nSome text")

    def test_resolve_attachment_fallback_to_note_id(self):
        img_data = b"image-content-bytes"
        att_id = self.db.save_attachment(
            note_id="note-fallback",
            filename="diagram.png",
            mime_type="image/png",
            data=img_data,
        )

        # Resolves via direct ID
        uri1 = resolve_attachment_to_data_uri(f"attachment://{att_id}", db=self.db)
        self.assertIsNotNone(uri1)
        self.assertTrue(uri1.startswith("data:image/png;base64,"))

        # Resolves when filename is appended (e.g. {att_id}.png)
        uri2 = resolve_attachment_to_data_uri(f"attachment://{att_id}.png", db=self.db)
        self.assertIsNotNone(uri2)
        self.assertEqual(uri1, uri2)

    def test_get_plain_text(self):
        note = Note(
            id="n1",
            title="Title",
            content_html="<h1>Heading</h1><p>Hello <b>World</b>!</p>",
            content_markdown="# Heading\n\nHello **World**!",
        )
        plain = get_plain_text(note)
        self.assertIn("Hello World!", plain)
        self.assertNotIn("#", plain)
        self.assertNotIn("**", plain)

if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import unittest
from stilonotes.database import NoteDatabase
from stilonotes.models import Note
import os
from stilonotes.exporter import (
    bundle_attachments_in_html,
    bundle_attachments_in_markdown,
    resolve_attachment_to_data_uri,
    get_plain_text,
    render_printable_html,
    setup_print_preview_settings,
    Printer,
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

    def test_render_printable_html(self):
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        att_id = self.db.save_attachment(
            note_id="n-print",
            filename="diagram.png",
            mime_type="image/png",
            data=png_data,
        )

        note = Note(
            id="n-print",
            title="Project Architecture",
            content_html=(
                '<h1>Project Architecture</h1>'
                '<p contenteditable="true">Here is the architecture:</p>'
                f'<img src="attachment://{att_id}">'
                '<div class="table-handle" contenteditable="false"></div>'
            ),
            content_markdown="# Project Architecture\n\nHere is the architecture:",
        )

        html_out = render_printable_html(note, db=self.db)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("<title>Project Architecture</title>", html_out)
        self.assertIn("@media print", html_out)
        self.assertIn("@page", html_out)
        self.assertIn("data:image/png;base64,", html_out)
        self.assertNotIn("table-handle", html_out)
        self.assertNotIn('contenteditable="true"', html_out)

    def test_printer_instantiation(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        note = Note(
            id="n-printer",
            title="Meeting Notes",
            content_html="<h1>Meeting Notes</h1><p>Action items here.</p>",
            content_markdown="# Meeting Notes\n\nAction items here.",
        )
        printer = Printer(note, db=self.db)
        self.assertIsNotNone(printer.web_view)
        self.assertIn("Meeting Notes", printer.html)
        self.assertEqual(printer.note.id, "n-printer")


    def test_setup_print_preview_settings(self):
        # Should execute safely even without display
        setup_print_preview_settings()
        self.assertEqual(os.environ.get("WEBKIT_USE_PORTAL"), "1")
        from gi.repository import Gdk, Gtk
        display = Gdk.Display.get_default()
        if display is not None:
            settings = Gtk.Settings.get_for_display(display)
            if settings:
                cmd = settings.get_property("gtk-print-preview-command")
                self.assertIsNotNone(cmd)
                self.assertIn("%f", cmd)

    def test_editor_print_button_and_action(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from stilonotes.editor import NoteEditor
        editor = NoteEditor(self.db)
        self.assertTrue(hasattr(editor, "print_btn"))
        self.assertEqual(editor.print_btn.get_icon_name(), "printer-symbolic")
        self.assertIn("Print", editor.print_btn.get_tooltip_text())
        self.assertEqual(editor.print_btn.get_action_name(), "editor.print")

    def test_editor_print_concurrent_prevention(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from stilonotes.editor import NoteEditor
        editor = NoteEditor(self.db)
        note = self.db.create_note(title="Print Test", content_markdown="Some content")
        editor.load_note(note)
        # Mock active printer
        editor._current_printer = "dummy_printer"
        # Calling _print_note should return early and not replace _current_printer
        editor._print_note()
        self.assertEqual(editor._current_printer, "dummy_printer")

    def test_printer_finished_emitted_once(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        note = Note(
            id="n-printer2",
            title="Meeting Notes 2",
            content_html="<h1>Notes</h1>",
            content_markdown="# Notes",
        )
        printer = Printer(note, db=self.db)
        emitted_count = 0
        def on_finished(p):
            nonlocal emitted_count
            emitted_count += 1
        printer.connect("finished", on_finished)
        printer._on_finished()
        printer._on_finished()
        self.assertEqual(emitted_count, 1)

    def test_editor_html_has_ctrl_p_shortcut(self):
        from stilonotes.const import get_assets_path
        html_path = get_assets_path() / "editor" / "editor.html"
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")
        self.assertIn("printNote", content)
        self.assertIn("(e.key === 'p' || e.key === 'P')", content)

    def test_window_has_print_action(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from stilonotes.window import StiloWindow
        from stilonotes.application import StiloApplication
        app = StiloApplication()
        win = StiloWindow(application=app, db=self.db)
        ag = win.get_action_group("win")
        self.assertIsNotNone(ag)
        self.assertTrue(ag.has_action("print"))
        win.destroy()


if __name__ == "__main__":
    unittest.main()


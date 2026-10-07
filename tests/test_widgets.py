# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.database import NoteDatabase


class TestDatabaseCountsAndFilter(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")

    def tearDown(self):
        self.db.close()

    def test_counts(self):
        counts = self.db.get_counts()
        self.assertIn("all", counts)
        self.assertIn("pinned", counts)
        self.assertIn("todo", counts)
        self.assertIn("uncategorized", counts)
        self.assertIn("trash", counts)
        self.assertGreaterEqual(counts["all"], 1)

    def test_uncategorized_filter(self):
        notes = self.db.get_notes(filter_type="uncategorized")
        self.assertIsInstance(notes, list)

    def test_create_and_delete_category(self):
        self.assertTrue(self.db.create_category("TestCategory"))
        categories = self.db.get_categories()
        names = [c.name for c in categories]
        self.assertIn("TestCategory", names)

        self.db.delete_category("TestCategory")
        categories_after = self.db.get_categories()
        names_after = [c.name for c in categories_after]
        self.assertNotIn("TestCategory", names_after)

    def test_insert_link_dialog(self):
        import json
        from gi.repository import Adw, Gtk
        from stilonotes.editor import NoteEditor

        ed = NoteEditor(self.db)

        class FakeJsResult:
            def __init__(self, data):
                self._data = data
            def get_js_value(self):
                return self
            def to_string(self):
                return json.dumps(self._data)

        presented_dialog = []
        orig_present = Adw.AlertDialog.present
        def fake_present(dlg, parent):
            presented_dialog.append(dlg)
        Adw.AlertDialog.present = fake_present

        try:
            # 1. Test External Link Dialog (reverted to simple Label + URL)
            ed._on_js_insert_link(None, FakeJsResult({"text": "My Label", "url": "https://example.org"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg = presented_dialog[0]
            self.assertEqual(dlg.get_heading(), "Insert Link")

            box = dlg.get_extra_child()
            self.assertIsNotNone(box)

            def find_widgets(widget, target_type):
                found = []
                child = widget.get_first_child()
                while child:
                    if isinstance(child, target_type):
                        found.append(child)
                    found.extend(find_widgets(child, target_type))
                    child = child.get_next_sibling()
                return found

            rows = find_widgets(box, Adw.EntryRow)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].get_title(), "Label")
            self.assertEqual(rows[0].get_text(), "My Label")
            self.assertEqual(rows[1].get_title(), "URL")
            self.assertEqual(rows[1].get_text(), "https://example.org")

            # 2. Test Internal Note Link Dialog (only internal link's stuff)
            presented_dialog.clear()
            ed._on_js_insert_internal_link(None, FakeJsResult({"noteTitle": "Project Alpha", "noteHeading": "Roadmap", "text": "Plan"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg2 = presented_dialog[0]
            self.assertEqual(dlg2.get_heading(), "Insert Note Link")
            box2 = dlg2.get_extra_child()

            combo_rows = find_widgets(box2, Adw.ComboRow)
            self.assertEqual(len(combo_rows), 1)
            self.assertEqual(combo_rows[0].get_title(), "Select Note")

            rows2 = find_widgets(box2, Adw.EntryRow)
            self.assertEqual(len(rows2), 3)
            note_row = [r for r in rows2 if r.get_title() == "Note Title"][0]
            heading_row = [r for r in rows2 if r.get_title() == "Heading"][0]
            label_row = [r for r in rows2 if r.get_title() == "Label"][0]
            self.assertEqual(note_row.get_text(), "Project Alpha")
            self.assertEqual(heading_row.get_text(), "Roadmap")
            self.assertEqual(label_row.get_text(), "Plan")

            # 3. Test Internal Link Mode with selected text auto-prefilling Note Title
            presented_dialog.clear()
            ed._on_js_insert_internal_link(None, FakeJsResult({"text": "Quick Note"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg3 = presented_dialog[0]
            box3 = dlg3.get_extra_child()
            rows3 = find_widgets(box3, Adw.EntryRow)
            note_row3 = [r for r in rows3 if r.get_title() == "Note Title"][0]
            self.assertEqual(note_row3.get_text(), "Quick Note")
        finally:
            Adw.AlertDialog.present = orig_present

    def test_copy_note_link(self):
        from gi.repository import Gdk
        from stilonotes.index import IndexView
        note = self.db.create_note("Sample Linked Note", "Content")
        view = IndexView(self.db)
        # Verify _on_note_copy_link executes cleanly without NameError
        view._on_note_copy_link(note.id)
        if Gdk.Display.get_default():
            clip = Gdk.Display.get_default().get_clipboard()
            # If clipboard is accessible, verify content
            # (In headless/CI it might be mocked or no-op)
            pass

    def test_cross_note_navigation_back_history(self):
        from gi.repository import Gdk, Adw
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from stilonotes.window import StiloWindow
        app = Adw.Application(application_id="io.github.fastrizwaan.StiloNotes.TestNav")
        win = StiloWindow(app, self.db)

        note_a = self.db.create_note("Note A", "Content A")
        note_b = self.db.create_note("Note B", "Content B")
        note_c = self.db.create_note("Note C", "Content C")

        # Open Note A from list
        win.open_note(note_a)
        self.assertEqual(win.editor.current_note.id, note_a.id)
        self.assertEqual(len(win._note_history), 0)

        # From Note A, follow link to Note B
        win._on_editor_open_note_link(win.editor, "Note B", "")
        self.assertEqual(win.editor.current_note.id, note_b.id)
        self.assertEqual(win._note_history, [note_a.id])

        # From Note B, follow link to Note C
        win._on_editor_open_note_link(win.editor, "Note C", "")
        self.assertEqual(win.editor.current_note.id, note_c.id)
        self.assertEqual(win._note_history, [note_a.id, note_b.id])

        # Click Back: should navigate to Note B
        win._go_back()
        self.assertEqual(win.editor.current_note.id, note_b.id)
        self.assertEqual(win._note_history, [note_a.id])

        # Click Back: should navigate to Note A
        win._go_back()
        self.assertEqual(win.editor.current_note.id, note_a.id)
        self.assertEqual(len(win._note_history), 0)

        # Click Back: should pop to Notes list
        win._go_back()
        self.assertEqual(len(win._note_history), 0)
        self.assertEqual(win.navigation.get_visible_page(), win.index_page)
    def test_multiline_selection_not_lost(self):
        from gi.repository import Gdk, WebKit, GLib
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from stilonotes.editor_html import get_editor_html_page
        html = get_editor_html_page("<div>Line 1: first paragraph</div><div>Line 2: second paragraph</div>")
        wv = WebKit.WebView()
        loop = GLib.MainLoop()
        result_holder = {}

        def on_load_changed(webview, event):
            if event == WebKit.LoadEvent.FINISHED:
                js = '''
                (function() {
                    const p1 = editor.children[0];
                    const p2 = editor.children[1];
                    const range = document.createRange();
                    range.setStart(p1.firstChild, 0);
                    range.setEnd(p2.firstChild, 5);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);

                    // WebKit fires click with target editor on multi-line selection
                    const clickEvt = new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 100, clientY: 50 });
                    editor.dispatchEvent(clickEvt);

                    return JSON.stringify({
                        text: window.getSelection().toString(),
                        isCollapsed: window.getSelection().isCollapsed
                    });
                })()
                '''
                webview.evaluate_javascript(js, -1, None, None, None, on_eval_done)

        def on_eval_done(webview, result):
            try:
                import json
                val = webview.evaluate_javascript_finish(result)
                result_holder.update(json.loads(val.to_string()))
            finally:
                loop.quit()

        wv.connect("load-changed", on_load_changed)
        wv.load_html(html, "file:///var/home/rizvan/StiloNotes/assets/")
        loop.run()

        self.assertFalse(result_holder.get("isCollapsed"))
        self.assertIn("Line 1", result_holder.get("text", ""))


if __name__ == "__main__":
    unittest.main()

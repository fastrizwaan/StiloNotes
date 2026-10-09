# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from teddynotes.database import NoteDatabase


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
        from teddynotes.editor import NoteEditor

        ed = NoteEditor(self.db)

        class FakeJsResult:
            def __init__(self, data):
                self._data = data
            def get_js_value(self):
                return self
            def to_string(self):
                return json.dumps(self._data)

        presented_dialog = []
        orig_alert_present = Adw.AlertDialog.present
        orig_dialog_present = Adw.Dialog.present
        def fake_present(dlg, parent):
            presented_dialog.append(dlg)
        Adw.AlertDialog.present = fake_present
        Adw.Dialog.present = fake_present

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
            ed._on_js_insert_internal_link(None, FakeJsResult({"noteTitle": "Project Alpha", "noteHeading": "Roadmap", "text": "Plan", "isEdit": True}))
            self.assertEqual(len(presented_dialog), 1)
            dlg2 = presented_dialog[0]
            self.assertEqual(dlg2.get_heading(), "Edit Note Link")
            self.assertTrue(dlg2.get_prefer_wide_layout())
            self.assertGreaterEqual(dlg2.get_content_width(), 460)
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

            # Verify standard GNOME dialog responses (Cancel, Save, Remove Link)
            self.assertTrue(dlg2.has_response("cancel"))
            self.assertTrue(dlg2.has_response("remove"))
            self.assertTrue(dlg2.has_response("insert"))
            self.assertEqual(dlg2.get_response_label("insert"), "Save")
            self.assertEqual(dlg2.get_response_label("remove"), "Remove Link")
            self.assertEqual(dlg2.get_response_label("cancel"), "Cancel")
            self.assertEqual(dlg2.get_response_appearance("insert"), Adw.ResponseAppearance.SUGGESTED)
            self.assertEqual(dlg2.get_response_appearance("remove"), Adw.ResponseAppearance.DESTRUCTIVE)

            # 3. Test Internal Link Mode with selected text auto-prefilling Note Title
            presented_dialog.clear()
            ed._on_js_insert_internal_link(None, FakeJsResult({"text": "Quick Note"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg3 = presented_dialog[0]
            self.assertEqual(dlg3.get_heading(), "Insert Note Link")
            self.assertTrue(dlg3.has_response("cancel"))
            self.assertFalse(dlg3.has_response("remove"))
            self.assertTrue(dlg3.has_response("insert"))
            self.assertEqual(dlg3.get_response_label("insert"), "Insert")
            self.assertEqual(dlg3.get_response_appearance("insert"), Adw.ResponseAppearance.SUGGESTED)
            box3 = dlg3.get_extra_child()
            rows3 = find_widgets(box3, Adw.EntryRow)
            note_row3 = [r for r in rows3 if r.get_title() == "Note Title"][0]
            self.assertEqual(note_row3.get_text(), "Quick Note")

            # 4. Test Heading Popover sizing and layout
            self.db.create_note("Project Gamma", content_markdown="# Project Gamma\n\n## Introduction\nText\n## Details\nMore text")
            presented_dialog.clear()
            ed._on_js_insert_internal_link(None, FakeJsResult({"noteTitle": "Project Gamma", "text": "Gamma Link"}))
            self.assertEqual(len(presented_dialog), 1)
            dlg4 = presented_dialog[0]
            box4 = dlg4.get_extra_child()
            rows4 = find_widgets(box4, Adw.EntryRow)
            heading_row4 = [r for r in rows4 if r.get_title() == "Heading"][0]

            menu_btns = find_widgets(heading_row4, Gtk.MenuButton)
            self.assertEqual(len(menu_btns), 1)
            heading_btn = menu_btns[0]
            self.assertTrue(heading_btn.get_visible())

            popover = heading_btn.get_popover()
            self.assertIsNotNone(popover)
            sw = popover.get_child()
            self.assertIsInstance(sw, Gtk.ScrolledWindow)
            h_policy, _v_policy = sw.get_policy()
            self.assertEqual(h_policy, Gtk.PolicyType.NEVER)
            self.assertTrue(sw.get_propagate_natural_width())
            self.assertTrue(sw.get_propagate_natural_height())
            self.assertGreaterEqual(sw.get_min_content_width(), 260)

            pop_box = sw.get_child()
            heading_btns = find_widgets(pop_box, Gtk.Button)
            self.assertEqual(len(heading_btns), 2)
            lbl1 = heading_btns[0].get_child()
            self.assertEqual(lbl1.get_label(), "Introduction")
            self.assertEqual(lbl1.get_xalign(), 0.0)
        finally:
            Adw.AlertDialog.present = orig_alert_present
            Adw.Dialog.present = orig_dialog_present

    def test_copy_note_link(self):
        from gi.repository import Gdk
        from teddynotes.index import IndexView
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

        from teddynotes.window import TeddyWindow
        app = Adw.Application(application_id="io.github.fastrizwaan.TeddyNotes.TestNav")
        win = TeddyWindow(app, self.db)

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

        from teddynotes.editor_html import get_editor_html_page
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
        from teddynotes.const import get_assets_path
        wv.load_html(html, f"file://{get_assets_path()}/")
        loop.run()

        self.assertFalse(result_holder.get("isCollapsed"))
        self.assertIn("Line 1", result_holder.get("text", ""))


class TestEditorContextMenuAndNavigation(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        from teddynotes.editor import NoteEditor
        self.editor = NoteEditor(self.db)

    def tearDown(self):
        self.db.close()

    def test_context_menu_blocks_reload_and_browser_navigation(self):
        import gi
        gi.require_version('WebKit', '6.0')
        from gi.repository import WebKit

        cm = WebKit.ContextMenu()
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.GO_BACK))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.GO_FORWARD))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.STOP))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.RELOAD))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY))

        # In edit mode
        self.editor.is_read_only = False
        res = self.editor._on_context_menu(self.editor.webview, cm, None)
        self.assertFalse(res)  # Shows menu
        actions = [it.get_stock_action() for it in cm.get_items()]
        self.assertNotIn(WebKit.ContextMenuAction.RELOAD, actions)
        self.assertNotIn(WebKit.ContextMenuAction.GO_BACK, actions)
        self.assertNotIn(WebKit.ContextMenuAction.GO_FORWARD, actions)
        self.assertNotIn(WebKit.ContextMenuAction.STOP, actions)
        self.assertIn(WebKit.ContextMenuAction.COPY, actions)

    def test_context_menu_read_only_mode(self):
        import gi
        gi.require_version('WebKit', '6.0')
        from gi.repository import WebKit

        cm = WebKit.ContextMenu()
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.RELOAD))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.CUT))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.PASTE))
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY))

        # In read-only mode
        self.editor.is_read_only = True
        res = self.editor._on_context_menu(self.editor.webview, cm, None)
        self.assertFalse(res)
        actions = [it.get_stock_action() for it in cm.get_items()]
        self.assertNotIn(WebKit.ContextMenuAction.RELOAD, actions)
        self.assertNotIn(WebKit.ContextMenuAction.CUT, actions)
        self.assertNotIn(WebKit.ContextMenuAction.PASTE, actions)
        self.assertIn(WebKit.ContextMenuAction.COPY, actions)

    def test_context_menu_empty_provides_select_all(self):
        import gi
        gi.require_version('WebKit', '6.0')
        from gi.repository import WebKit

        cm = WebKit.ContextMenu()
        cm.append(WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.RELOAD))

        self.editor.is_read_only = True
        res = self.editor._on_context_menu(self.editor.webview, cm, None)
        self.assertFalse(res)
        actions = [it.get_stock_action() for it in cm.get_items()]
        self.assertNotIn(WebKit.ContextMenuAction.RELOAD, actions)
        self.assertIn(WebKit.ContextMenuAction.SELECT_ALL, actions)

    def test_decide_policy_blocks_reload_and_back_forward(self):
        import gi
        gi.require_version('WebKit', '6.0')
        from gi.repository import WebKit

        class MockAction:
            def __init__(self, nav_type, uri=None):
                self._nav_type = nav_type
                self._uri = uri
            def get_navigation_type(self):
                return self._nav_type
            def get_request(self):
                class Req:
                    def __init__(self, u): self._u = u
                    def get_uri(self): return self._u
                return Req(self._uri) if self._uri else None

        class MockDecision:
            def __init__(self, action):
                self._action = action
                self.ignored = False
            def get_navigation_action(self):
                return self._action
            def ignore(self):
                self.ignored = True

        # Test Reload
        dec_reload = MockDecision(MockAction(WebKit.NavigationType.RELOAD, "file:///assets/"))
        res = self.editor._on_decide_policy(self.editor.webview, dec_reload, WebKit.PolicyDecisionType.NAVIGATION_ACTION)
        self.assertTrue(res)
        self.assertTrue(dec_reload.ignored)

        # Test Back/Forward
        dec_bf = MockDecision(MockAction(WebKit.NavigationType.BACK_FORWARD, "file:///assets/"))
        res = self.editor._on_decide_policy(self.editor.webview, dec_bf, WebKit.PolicyDecisionType.NAVIGATION_ACTION)
        self.assertTrue(res)
        self.assertTrue(dec_bf.ignored)

        # Test Link clicked
        dec_link = MockDecision(MockAction(WebKit.NavigationType.LINK_CLICKED, "file:///assets/editor/"))
        res = self.editor._on_decide_policy(self.editor.webview, dec_link, WebKit.PolicyDecisionType.NAVIGATION_ACTION)
        self.assertTrue(res)
        self.assertTrue(dec_link.ignored)

        # Test Programmatic load_html (OTHER)
        dec_other = MockDecision(MockAction(WebKit.NavigationType.OTHER, "file:///assets/editor/editor.html"))
        res = self.editor._on_decide_policy(self.editor.webview, dec_other, WebKit.PolicyDecisionType.NAVIGATION_ACTION)
        self.assertFalse(res)
        self.assertFalse(dec_other.ignored)

    def test_webview_key_pressed_blocks_f5_and_ctrl_r(self):
        import gi
        gi.require_version('Gdk', '4.0')
        from gi.repository import Gdk

        # F5
        self.assertTrue(self.editor._on_webview_key_pressed(None, Gdk.KEY_F5, 0, Gdk.ModifierType(0)))
        # Ctrl+R
        self.assertTrue(self.editor._on_webview_key_pressed(None, Gdk.KEY_r, 0, Gdk.ModifierType.CONTROL_MASK))
        # Normal key (e.g. typing 'a')
        self.assertFalse(self.editor._on_webview_key_pressed(None, Gdk.KEY_a, 0, Gdk.ModifierType(0)))
        # Ctrl+C
        self.assertFalse(self.editor._on_webview_key_pressed(None, Gdk.KEY_c, 0, Gdk.ModifierType.CONTROL_MASK))


if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import html
import os
import re
from typing import Callable, List, Optional
from gi.repository import Gtk, Gio, GLib

from stilonotes.models import Note
from stilonotes.markdown_utils import html_to_markdown

def get_plain_text(note: Note) -> str:
    """Extract plain text from note."""
    if note.content_markdown:
        # Strip markdown syntax
        s = note.content_markdown
        s = re.sub(r'#+\s*', '', s)
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
        s = re.sub(r'[*_~`]', '', s)
        return s
    clean = re.sub(r'<[^>]+>', ' ', note.content_html)
    return html.unescape(clean)

def export_note_dialog(parent_window: Gtk.Window, note: Note, fmt: str = "md", on_complete: Optional[Callable[[str], None]] = None):
    """Present a file save dialog to export note to file."""
    dialog = Gtk.FileDialog()

    clean_title = re.sub(r'[\\/*?:"<>|]', "", note.title or "Untitled")
    extension = fmt.lower()
    default_name = f"{clean_title}.{extension}"
    dialog.set_initial_name(default_name)

    # Filter
    filters = Gio.ListStore.new(Gtk.FileFilter)
    file_filter = Gtk.FileFilter()
    if extension == "md":
        file_filter.set_name("Markdown Document (*.md)")
        file_filter.add_pattern("*.md")
    elif extension == "html":
        file_filter.set_name("HTML Document (*.html)")
        file_filter.add_pattern("*.html")
    else:
        file_filter.set_name("Plain Text Document (*.txt)")
        file_filter.add_pattern("*.txt")
    filters.append(file_filter)
    dialog.set_filters(filters)

    def on_save_finish(dialog, result):
        try:
            target_file = dialog.save_finish(result)
            if target_file:
                path = target_file.get_path()
                if extension == "md":
                    content = note.content_markdown or html_to_markdown(note.content_html)
                elif extension == "html":
                    content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(note.title)}</title>
<style>
body {{ font-family: -apple-system, Cantarell, Inter, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; }}
pre {{ background: #f4f4f4; padding: 12px; border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; }}
th {{ background: #f8f8f8; }}
</style>
</head>
<body>
{note.content_html}
</body>
</html>"""
                else:
                    content = get_plain_text(note)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

                if on_complete:
                    on_complete(f"Exported to {target_file.get_basename()}")
        except Exception as e:
            print("Export cancelled or failed:", e)

    dialog.save(parent_window, None, on_save_finish)

def export_notes_dialog(parent_window: Gtk.Window, notes: List[Note], on_complete: Optional[Callable[[str], None]] = None):
    """Present a folder selection dialog to export multiple notes as Markdown files."""
    if not notes:
        return
    dialog = Gtk.FileDialog()
    dialog.set_title("Export Selected Notes")

    def on_folder_finish(dialog, result):
        try:
            target_folder = dialog.select_folder_finish(result)
            if target_folder:
                folder_path = target_folder.get_path()
                saved_count = 0
                for note in notes:
                    clean_title = re.sub(r'[\\/*?:"<>|]', "", note.title or "Untitled").strip() or "Untitled"
                    filename = f"{clean_title}.md"
                    filepath = os.path.join(folder_path, filename)
                    counter = 1
                    while os.path.exists(filepath):
                        filename = f"{clean_title} ({counter}).md"
                        filepath = os.path.join(folder_path, filename)
                        counter += 1

                    content = note.content_markdown or html_to_markdown(note.content_html)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    saved_count += 1

                if on_complete:
                    on_complete(f"Exported {saved_count} notes to {target_folder.get_basename()}")
        except Exception as e:
            print("Folder export cancelled or failed:", e)

    dialog.select_folder(parent_window, None, on_folder_finish)

# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import html
import mimetypes
import os
import re
import urllib.parse
from typing import Any, Callable, List, Optional
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

def resolve_attachment_to_data_uri(
    uri: str,
    db: Optional[Any] = None,
    note_id: Optional[str] = None
) -> Optional[str]:
    """Resolve an attachment://, attachment:, or file:// URI to a base64 data URI."""
    if not uri:
        return None

    clean_uri = uri.strip()

    # Case 1: Attachment scheme
    if clean_uri.startswith("attachment://") or clean_uri.startswith("attachment:"):
        prefix = "attachment://" if clean_uri.startswith("attachment://") else "attachment:"
        path = clean_uri[len(prefix):]
        # Remove any path separators, query params, hash
        att_id = path.split("/")[0].split("?")[0].split("#")[0]
        if not att_id:
            return None

        att = None
        if db:
            try:
                # 1. Direct ID lookup
                att = db.get_attachment(att_id)
                # 2. Try stripping extension if ID contains a dot (e.g. uuid.png)
                if not att and "." in att_id:
                    att = db.get_attachment(att_id.rsplit(".", 1)[0])
                # 3. Query attachments for note or matching filename/id
                if not att and hasattr(db, "get_connection"):
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM attachments WHERE id = ? OR filename = ?", (att_id, att_id))
                        row = cursor.fetchone()
                        if not row and note_id:
                            cursor.execute("SELECT * FROM attachments WHERE note_id = ?", (note_id,))
                            rows = cursor.fetchall()
                            for r in rows:
                                if r["id"] == att_id or r["filename"] == att_id:
                                    row = r
                                    break
                            else:
                                if len(rows) == 1:
                                    row = rows[0]
                        if row:
                            att = {
                                "id": row["id"],
                                "mime_type": row["mime_type"],
                                "data": row["data"],
                                "filename": row["filename"],
                            }
            except Exception as e:
                print("Error fetching attachment:", e)

        if att and att.get("data"):
            data = att["data"]
            mime = att.get("mime_type")
            if not mime or mime == "application/octet-stream":
                filename = att.get("filename", "")
                guessed, _ = mimetypes.guess_type(filename)
                if guessed:
                    mime = guessed
                elif data.startswith(b"<svg") or b"<svg" in data[:100]:
                    mime = "image/svg+xml"
                elif data.startswith(b"\x89PNG"):
                    mime = "image/png"
                elif data.startswith(b"\xff\xd8\xff"):
                    mime = "image/jpeg"
                elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
                    mime = "image/gif"
                elif data.startswith(b"RIFF") and b"WEBP" in data[:16]:
                    mime = "image/webp"
                else:
                    mime = "image/png"

            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"

    # Case 2: Local file:// or absolute path
    elif clean_uri.startswith("file://") or (clean_uri.startswith("/") and os.path.isabs(clean_uri)):
        local_path = clean_uri[len("file://"):] if clean_uri.startswith("file://") else clean_uri
        local_path = urllib.parse.unquote(local_path)
        if os.path.isfile(local_path):
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                mime, _ = mimetypes.guess_type(local_path)
                if not mime:
                    if local_path.lower().endswith(".svg") or data.startswith(b"<svg") or b"<svg" in data[:100]:
                        mime = "image/svg+xml"
                    else:
                        mime = "image/png"
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
            except Exception as e:
                print("Error reading file for bundling:", e)

    return None

def bundle_attachments_in_html(html_str: str, db: Optional[Any] = None, note_id: Optional[str] = None) -> str:
    """Replace all attachment://, attachment:, and local file:// src attributes with base64 data URIs."""
    if not html_str:
        return ""

    def _replace_src(match):
        prefix = match.group(1)
        quote = match.group(2)
        uri = match.group(3)
        data_uri = resolve_attachment_to_data_uri(uri, db=db, note_id=note_id)
        if data_uri:
            q = quote if quote else '"'
            return f"{prefix}{q}{data_uri}{q}"
        return match.group(0)

    pattern = re.compile(
        r'(src=)(["\']?)(attachment://[^"\'\s>]+|attachment:[^"\'\s>]+|file://[^"\'\s>]+)\2',
        re.IGNORECASE
    )
    return pattern.sub(_replace_src, html_str)

def bundle_attachments_in_markdown(md_str: str, db: Optional[Any] = None, note_id: Optional[str] = None) -> str:
    """Replace all attachment://, attachment:, and local file:// URIs in Markdown image syntax with base64 data URIs."""
    if not md_str:
        return ""

    def _replace_md(match):
        alt = match.group(1)
        uri = match.group(2)
        data_uri = resolve_attachment_to_data_uri(uri, db=db, note_id=note_id)
        if data_uri:
            return f"![{alt}]({data_uri})"
        return match.group(0)

    pattern = re.compile(
        r'!\[([^\]]*)\]\((attachment://[^)\s]+|attachment:[^)\s]+|file://[^)\s]+)\)',
        re.IGNORECASE
    )
    return pattern.sub(_replace_md, md_str)

def export_note_dialog(parent_window: Gtk.Window, note: Note, fmt: str = "md", on_complete: Optional[Callable[[str], None]] = None, db: Optional[Any] = None):
    """Present a file save dialog to export note to file."""
    dialog = Gtk.FileDialog()

    clean_title = re.sub(r'[\\/*?:"<>|]', "", note.title or "Untitled").strip() or "Untitled"
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
                database = db
                if database is None:
                    try:
                        from stilonotes.database import NoteDatabase
                        database = NoteDatabase()
                    except Exception:
                        database = None

                if extension == "md":
                    raw_content = note.content_markdown or html_to_markdown(note.content_html)
                    content = bundle_attachments_in_markdown(raw_content, db=database, note_id=note.id)
                elif extension == "html":
                    clean_html = note.content_html or ""
                    # Strip contenteditable attributes from elements
                    clean_html = re.sub(r'\s*contenteditable=(["\'])?(?:true|false)\1', '', clean_html)
                    # Strip resize handles or editor UI artifacts
                    clean_html = re.sub(
                        r'<div[^>]*class=["\'][^"\']*(?:table-handle|image-handle|col-resize-handle)[^"\']*["\'][^>]*>.*?</div>',
                        '',
                        clean_html
                    )
                    bundled_html = bundle_attachments_in_html(clean_html, db=database, note_id=note.id)
                    content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(note.title or "Untitled Note")}</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Cantarell, Inter, sans-serif;
  max-width: 760px;
  margin: 40px auto;
  padding: 0 20px;
  line-height: 1.6;
  color: #222;
}}
pre {{
  background: #f4f4f4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}}
code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
  background: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
}}
pre code {{
  background: none;
  padding: 0;
}}
blockquote {{
  border-left: 4px solid #ddd;
  margin: 16px 0;
  padding-left: 14px;
  color: #555;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}}
th, td {{
  border: 1px solid #ddd;
  padding: 8px 12px;
}}
th {{
  background: #f8f8f8;
  text-align: left;
}}
.stilo-img-wrapper {{
  display: inline-block;
  max-width: 100%;
  margin: 12px 0;
}}
.stilo-img, img {{
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  display: block;
}}
.stilo-task {{
  display: flex;
  align-items: baseline;
  margin: 4px 0;
}}
.stilo-checkbox {{
  margin-right: 8px;
}}
h5 {{ font-size: 1.1em; font-weight: 600; margin: 14px 0 6px; }}
h6 {{ font-size: 1.0em; font-weight: 600; margin: 12px 0 4px; color: #666; }}
sub {{ font-size: 75%; line-height: 0; position: relative; vertical-align: baseline; bottom: -0.25em; }}
sup {{ font-size: 75%; line-height: 0; position: relative; vertical-align: baseline; top: -0.5em; }}
mark {{ background-color: #fef08a; padding: 1px 3px; border-radius: 3px; }}
del {{ text-decoration: line-through; opacity: 0.75; }}
dl {{ margin: 14px 0; }}
dt {{ font-weight: 600; margin-top: 10px; }}
dd {{ margin-left: 24px; margin-bottom: 6px; }}
.stilo-footnotes {{ margin-top: 28px; font-size: 0.9em; border-top: 1px solid #ddd; padding-top: 14px; }}
.stilo-footnote-ref {{ font-size: 0.75em; vertical-align: super; font-weight: 600; }}
.stilo-footnote-backref {{ text-decoration: none; margin-left: 6px; }}
</style>
</head>
<body>
{bundled_html}
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

def export_notes_dialog(parent_window: Gtk.Window, notes: List[Note], on_complete: Optional[Callable[[str], None]] = None, db: Optional[Any] = None):
    """Present a folder selection dialog to export multiple notes as Markdown files."""
    if not notes:
        return
    dialog = Gtk.FileDialog()
    dialog.set_title("Export Selected Notes")

    database = db
    if database is None:
        try:
            from stilonotes.database import NoteDatabase
            database = NoteDatabase()
        except Exception:
            database = None

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

                    raw_content = note.content_markdown or html_to_markdown(note.content_html)
                    content = bundle_attachments_in_markdown(raw_content, db=database, note_id=note.id)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    saved_count += 1

                if on_complete:
                    on_complete(f"Exported {saved_count} notes to {target_folder.get_basename()}")
        except Exception as e:
            print("Folder export cancelled or failed:", e)

    dialog.select_folder(parent_window, None, on_folder_finish)


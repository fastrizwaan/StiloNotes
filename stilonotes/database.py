# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import json
import os
import re
import sqlite3
import threading
import time
import urllib.parse
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from gi.repository import GLib

from stilonotes.models import Note, Category
from stilonotes.markdown_utils import (
    extract_title_and_excerpt,
    extract_tags,
    extract_categories,
    extract_table_data,
    check_has_todo,
    check_has_list,
    markdown_to_html,
    html_to_markdown,
)

class NoteDatabase:
    """High-performance SQLite Database manager for Stilo Notes."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            data_dir = Path(GLib.get_user_data_dir()) / "stilonotes"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "stilonotes.db"

        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._change_listeners = []

        self._init_db()

    def add_change_listener(self, callback):
        """Register a callback for database change notifications: callback(event_type, data, sender)."""
        if callback not in self._change_listeners:
            self._change_listeners.append(callback)

    def remove_change_listener(self, callback):
        """Unregister a database change callback."""
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_change(self, event_type: str, data: Optional[Dict[str, Any]] = None, sender: Any = None):
        """Notify all registered listeners on the GLib main loop."""
        if not self._change_listeners:
            return
        payload = data or {}
        listeners = list(self._change_listeners)

        def dispatch():
            for cb in listeners:
                try:
                    cb(event_type, payload, sender)
                except Exception as e:
                    print(f"Error in db change listener for {event_type}:", e)
            return False

        try:
            GLib.idle_add(dispatch)
        except Exception:
            dispatch()

    def _register_functions(self, conn: sqlite3.Connection):
        """Register custom SQLite functions for fast content classification."""
        conn.create_function(
            "has_todo_fn", 2,
            lambda md, html: 1 if (check_has_todo(md) or check_has_todo(html)) else 0
        )
        conn.create_function(
            "has_list_fn", 2,
            lambda md, html: 1 if (check_has_list(md) or check_has_list(html)) else 0
        )

    @contextmanager
    def get_connection(self):
        """Thread-safe context manager for persistent SQLite connection."""
        with self._lock:
            if self._conn is None:
                is_mem = str(self.db_path) == ":memory:"
                conn_path = ":memory:" if is_mem else str(self.db_path)
                conn = sqlite3.connect(conn_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._register_functions(conn)

                # Performance tuning pragmas
                if not is_mem:
                    conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    conn.execute("PRAGMA temp_store = MEMORY")
                    conn.execute("PRAGMA cache_size = -64000")
                conn.execute("PRAGMA busy_timeout = 5000")
                self._conn = conn

            yield self._conn

    def close(self):
        """Cleanly close database connection and free resources."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def __del__(self):
        self.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Notes table - content_markdown is the single source of truth
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT,
                content_html TEXT,
                content_markdown TEXT,
                excerpt TEXT,
                category TEXT DEFAULT '',
                tags TEXT,
                is_pinned INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_trashed INTEGER DEFAULT 0,
                has_todo INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
            """)

            # Attachments table for storing images and media as binary blobs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                note_id TEXT,
                filename TEXT,
                mime_type TEXT,
                data BLOB,
                size_bytes INTEGER,
                created_at REAL
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_note ON attachments (note_id)")

            # Categories table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                icon TEXT DEFAULT 'folder-symbolic',
                color TEXT DEFAULT '',
                created_at REAL
            )
            """)

            # App settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

            # Indices for instant lookups and sorting
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes (updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed ON notes (is_trashed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes (is_pinned)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_category ON notes (category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed_pinned_updated ON notes (is_trashed, is_pinned, updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed_cat ON notes (is_trashed, category)")

            # Migrate legacy notes if content_markdown is empty but content_html exists
            cursor.execute("""
            SELECT id, content_html FROM notes
            WHERE (content_markdown IS NULL OR content_markdown = '')
              AND (content_html IS NOT NULL AND content_html != '')
            """)
            legacy_notes = cursor.fetchall()
            for r in legacy_notes:
                md = html_to_markdown(r["content_html"])
                cursor.execute("UPDATE notes SET content_markdown = ? WHERE id = ?", (md, r["id"]))

            # Ensure notes with checklist items have has_todo set to 1
            cursor.execute("SELECT id, content_markdown, content_html, has_todo FROM notes WHERE has_todo = 0 AND is_trashed = 0")
            for r in cursor.fetchall():
                if check_has_todo(r["content_markdown"]) or check_has_todo(r["content_html"]):
                    cursor.execute("UPDATE notes SET has_todo = 1 WHERE id = ?", (r["id"],))

            conn.commit()

            # Seed initial sample note if empty
            cursor.execute("SELECT COUNT(*) as cnt FROM notes")
            if cursor.fetchone()["cnt"] == 0:
                self._seed_welcome_notes(conn)

    def _seed_welcome_notes(self, conn: sqlite3.Connection):
        """Create a delightful welcome note showcasing Stilo Notes features."""
        now = time.time()
        note_id = str(uuid.uuid4())
        title = "Welcome to Stilo Notes 🖊️"

        md_content = """# Welcome to Stilo Notes 🖊️

**Stilo Notes** brings together the clean, distraction-free **GNOME Adwaita** interface of Iotas with the dynamic **WebKit Markdown** live rendering engine!

### ✨ Key Features
- **Dynamic Markdown Parsing**: Type markdown on the fly and watch it format live!
- **Interactive Checklists**: Click checkboxes directly in the editor to mark tasks complete.
- **Fast Sidebar Organization**: Group notes by Categories or Favorites.
- **Real-time Statistics**: View word count, characters, and reading time.
- **Export Anywhere**: Export cleanly to Markdown, HTML, or Plain Text.

### 📝 Try These Quick Formatting Shortcuts
- Type `# ` for Heading 1, `## ` for Heading 2, or `### ` for Heading 3
- Type `- [ ] ` to start an interactive checklist
- Type `* ` or `- ` for bullet lists, `1. ` for numbered lists
- Type `> ` for blockquotes
- Type `---` on an empty line for a divider
- Type `**bold**`, `*italic*`, `==highlight==`, or `~~strikethrough~~`

### ☑️ Your First Checklist
- [x] Launch Stilo Notes
- [ ] Try typing a new thought below
- [ ] Toggle dark and light mode
- [ ] Create a custom category in the sidebar

Enjoy writing with Stilo Notes!
"""
        html_content = markdown_to_html(md_content)
        title, excerpt = extract_title_and_excerpt(md_content, html_content)
        tags = json.dumps(["welcome", "notes"])

        conn.execute("""
        INSERT INTO notes (
            id, title, content_html, content_markdown, excerpt, category,
            tags, is_pinned, is_archived, is_trashed, has_todo, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id, title, html_content, md_content, excerpt, "Personal",
            tags, 1, 0, 0, 1, now, now
        ))

        # Insert sample category
        conn.execute("INSERT OR IGNORE INTO categories (id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                     (str(uuid.uuid4()), "Personal", "user-home-symbolic", now))
        conn.execute("INSERT OR IGNORE INTO categories (id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                     (str(uuid.uuid4()), "Work", "work-symbolic", now))

        conn.commit()

    def get_notes(
        self,
        filter_type: str = "all",
        category_name: str = "",
        tag_name: str = "",
        search_query: str = ""
    ) -> List[Note]:
        """Fetch notes for list display without loading massive content fields into memory."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Scalability: Select only metadata needed for list rendering (no content blobs)
            query = """
            SELECT id, title, excerpt, category, tags, is_pinned, is_archived, is_trashed,
                   has_todo, created_at, updated_at
            FROM notes WHERE 1=1
            """
            params: List[Any] = []

            # Trash filtering
            if filter_type == "trash":
                query += " AND is_trashed = 1"
            else:
                query += " AND is_trashed = 0"

            # Category / Tab filters
            if filter_type in ("pinned", "favorites"):
                query += " AND is_pinned = 1"
            elif filter_type in ("todo", "todos"):
                query += " AND (has_todo = 1 OR has_todo_fn(content_markdown, content_html) = 1)"
            elif filter_type in ("list", "lists"):
                query += " AND has_list_fn(content_markdown, content_html) = 1"
            elif filter_type in ("recent", "recents"):
                recent_cutoff = time.time() - (7 * 86400)
                query += " AND updated_at >= ?"
                params.append(recent_cutoff)
            elif filter_type == "uncategorized":
                query += " AND (category = '' OR category IS NULL)"
            elif filter_type == "category" and category_name:
                query += " AND (category = ? OR category LIKE ?)"
                params.append(category_name)
                params.append(category_name + "/%")
            elif (filter_type == "tag" and (category_name or tag_name)) or tag_name:
                t = (tag_name or category_name).strip().lstrip("#").lower()
                query += " AND (tags LIKE ? OR content_markdown LIKE ?)"
                params.append(f'%"{t}"%')
                params.append(f'%#{t}%')

            # Search query
            if search_query:
                q = f"%{search_query.strip()}%"
                query += " AND (title LIKE ? OR excerpt LIKE ? OR content_markdown LIKE ?)"
                params.extend([q, q, q])

            # Pinned notes appear first, then sorted by updated_at descending
            query += " ORDER BY is_pinned DESC, updated_at DESC"

            cursor.execute(query, params)
            return [Note.from_row(row) for row in cursor.fetchall()]

    def get_note(self, note_id: str) -> Optional[Note]:
        """Retrieve single note by ID with full content (Markdown as authoritative source)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if not row:
                return None

            note = Note.from_row(row)
            # Ensure content_html is dynamically synchronized with canonical Markdown
            if note.content_markdown and not note.content_html:
                note.content_html = markdown_to_html(note.content_markdown)
            elif not note.content_markdown and note.content_html:
                note.content_markdown = html_to_markdown(note.content_html)
            return note

    def save_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content_html: Optional[str] = None,
        content_markdown: Optional[str] = None,
        excerpt: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        is_trashed: Optional[bool] = None,
        has_todo: Optional[bool] = None,
        sender: Any = None,
    ) -> Note:
        """Save note with Markdown as the authoritative single source of truth."""
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()

            if row:
                existing = Note.from_row(row)
                # Markdown is canonical
                if content_markdown is not None:
                    new_md = content_markdown
                elif content_html is not None:
                    new_md = html_to_markdown(content_html)
                else:
                    new_md = existing.content_markdown

                # Synchronize HTML from canonical markdown
                new_html = content_html if content_html is not None else markdown_to_html(new_md)

                # Avoid redundant regex extraction when title/excerpt already supplied
                if title is not None and title != "Untitled Note" and excerpt is not None:
                    new_title = title
                    new_excerpt = excerpt
                else:
                    extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                    new_title = title if (title is not None and title != "Untitled Note") else (
                        extracted_title or existing.title or "Untitled Note"
                    )
                    new_excerpt = excerpt if excerpt is not None else extracted_excerpt

                extracted_tags = extract_tags(new_md or new_html)
                if tags is not None:
                    new_tags = list(dict.fromkeys(tags + extracted_tags))
                else:
                    new_tags = extracted_tags

                extracted_cats = extract_categories(new_md or new_html)
                if category is not None:
                    new_category = category
                elif extracted_cats:
                    new_category = extracted_cats[0]
                    self._create_category_sync(conn, new_category)
                else:
                    new_category = existing.category
                new_pinned = int(is_pinned if is_pinned is not None else existing.is_pinned)
                new_archived = int(is_archived if is_archived is not None else existing.is_archived)
                new_trashed = int(is_trashed if is_trashed is not None else existing.is_trashed)
                if has_todo or check_has_todo(new_md) or check_has_todo(new_html):
                    new_todo = 1
                else:
                    new_todo = 0

                cursor.execute("""
                UPDATE notes SET
                    title = ?,
                    content_html = ?,
                    content_markdown = ?,
                    excerpt = ?,
                    category = ?,
                    tags = ?,
                    is_pinned = ?,
                    is_archived = ?,
                    is_trashed = ?,
                    has_todo = ?,
                    updated_at = ?
                WHERE id = ?
                """, (
                    new_title,
                    new_html,
                    new_md,
                    new_excerpt,
                    new_category,
                    json.dumps(new_tags),
                    new_pinned,
                    new_archived,
                    new_trashed,
                    new_todo,
                    now,
                    note_id
                ))
            else:
                if content_markdown is not None:
                    new_md = content_markdown
                elif content_html:
                    new_md = html_to_markdown(content_html)
                else:
                    new_md = ""

                new_html = content_html or markdown_to_html(new_md)

                if title and title != "Untitled Note" and excerpt is not None:
                    new_title = title
                    new_excerpt = excerpt
                else:
                    extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                    new_title = title if (title and title != "Untitled Note") else (extracted_title or "Untitled Note")
                    new_excerpt = excerpt if excerpt is not None else extracted_excerpt

                extracted_tags = extract_tags(new_md or new_html)
                if tags is not None:
                    new_tags = list(dict.fromkeys(tags + extracted_tags))
                else:
                    new_tags = extracted_tags
                new_category = category or ""
                if not new_category:
                    extracted_cats = extract_categories(new_md or new_html)
                    if extracted_cats:
                        new_category = extracted_cats[0]
                        self._create_category_sync(conn, new_category)
                new_pinned = int(is_pinned or 0)
                new_archived = int(is_archived or 0)
                new_trashed = int(is_trashed or 0)
                if has_todo or check_has_todo(new_md) or check_has_todo(new_html):
                    new_todo = 1
                else:
                    new_todo = 0

                cursor.execute("""
                INSERT INTO notes (
                    id, title, content_html, content_markdown, excerpt, category,
                    tags, is_pinned, is_archived, is_trashed, has_todo, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    note_id,
                    new_title,
                    new_html,
                    new_md,
                    new_excerpt,
                    new_category,
                    json.dumps(new_tags),
                    new_pinned,
                    new_archived,
                    new_trashed,
                    new_todo,
                    now,
                    now
                ))

            # Prune attachments no longer referenced in note content
            if new_html is not None or new_md is not None:
                referenced_att_ids = set()
                for c in (new_html or "", new_md or ""):
                    for m in re.finditer(r'attachment://([a-zA-Z0-9_\-\.\+]+)', c):
                        referenced_att_ids.add(m.group(1).split('/')[0].split('?')[0])
                    for m in re.finditer(r'attachment:([a-zA-Z0-9_\-\.\+]+)', c):
                        referenced_att_ids.add(m.group(1).split('/')[0].split('?')[0])
                if referenced_att_ids:
                    placeholders = ','.join('?' for _ in referenced_att_ids)
                    cursor.execute(
                        f"DELETE FROM attachments WHERE note_id = ? AND id NOT IN ({placeholders})",
                        [note_id] + list(referenced_att_ids)
                    )
                else:
                    cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))

            conn.commit()
            saved_note = Note(
                id=note_id,
                title=new_title,
                content_html=new_html,
                content_markdown=new_md,
                excerpt=new_excerpt,
                category=new_category,
                tags=new_tags,
                is_pinned=bool(new_pinned),
                is_archived=bool(new_archived),
                is_trashed=bool(new_trashed),
                has_todo=bool(new_todo),
                created_at=row["created_at"] if row else now,
                updated_at=now,
            )
            self._notify_change("note-saved", {"note_id": note_id, "note": saved_note}, sender=sender)
            return saved_note

    def create_note(self, title: str = "Untitled Note", category: str = "", initial_text: str = "", sender: Any = None) -> Note:
        """Create a new note."""
        note_id = str(uuid.uuid4())
        md_content = initial_text or (f"# {title}\n\n" if title != "Untitled Note" else "")
        html_content = markdown_to_html(md_content) if md_content else f"<h1>{title}</h1><div><br></div>"
        return self.save_note(
            note_id=note_id,
            title=title,
            category=category,
            content_html=html_content,
            content_markdown=md_content,
            sender=sender
        )

    def delete_note(self, note_id: str, permanent: bool = False, sender: Any = None):
        """Move note to trash, or delete permanently."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if permanent:
                cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))
            else:
                cursor.execute("UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()
        self._notify_change("note-deleted", {"note_id": note_id, "permanent": permanent}, sender=sender)

    def restore_note(self, note_id: str, sender: Any = None):
        """Restore note from trash."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()
        self._notify_change("note-restored", {"note_id": note_id}, sender=sender)

    def empty_trash(self, sender: Any = None) -> int:
        """Permanently delete all notes in trash along with their attachments."""
        deleted_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM notes WHERE is_trashed = 1")
            rows = cursor.fetchall()
            if rows:
                trashed_ids = [r["id"] for r in rows]
                deleted_count = len(trashed_ids)
                placeholders = ",".join("?" for _ in trashed_ids)
                cursor.execute(f"DELETE FROM attachments WHERE note_id IN ({placeholders})", trashed_ids)
                cursor.execute("DELETE FROM notes WHERE is_trashed = 1")
                conn.commit()
        if deleted_count > 0:
            self._notify_change("trash-emptied", {"count": deleted_count}, sender=sender)
        return deleted_count

    def set_note_pinned(self, note_id: str, is_pinned: bool, sender: Any = None):
        """Set pinned status directly."""
        val = 1 if is_pinned else 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (val, time.time(), note_id))
            conn.commit()
        self._notify_change("note-pin-toggled", {"note_id": note_id, "is_pinned": bool(val)}, sender=sender)

    def set_notes_pinned(self, note_ids: List[str], is_pinned: bool, sender: Any = None):
        """Set pinned status for multiple notes."""
        if not note_ids:
            return
        val = 1 if is_pinned else 0
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id IN ({placeholders})", [val, now] + note_ids)
            conn.commit()
        for nid in note_ids:
            self._notify_change("note-pin-toggled", {"note_id": nid, "is_pinned": bool(val)}, sender=sender)

    def set_note_category(self, note_id: str, category: str, sender: Any = None):
        """Set category for a single note."""
        clean_cat = category.strip()
        if clean_cat:
            self.create_category(clean_cat)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET category = ?, updated_at = ? WHERE id = ?", (clean_cat, time.time(), note_id))
            conn.commit()
        self._notify_change("category-changed", {"note_id": note_id, "category": clean_cat}, sender=sender)

    def set_notes_category(self, note_ids: List[str], category: str, sender: Any = None):
        """Set category for multiple notes."""
        if not note_ids:
            return
        clean_cat = category.strip()
        if clean_cat:
            self.create_category(clean_cat)
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET category = ?, updated_at = ? WHERE id IN ({placeholders})", [clean_cat, now] + note_ids)
            conn.commit()
        self._notify_change("category-changed", {"note_ids": note_ids, "category": clean_cat}, sender=sender)

    def delete_notes(self, note_ids: List[str], permanent: bool = False, sender: Any = None):
        """Move multiple notes to trash, or delete permanently."""
        if not note_ids:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            if permanent:
                cursor.execute(f"DELETE FROM notes WHERE id IN ({placeholders})", note_ids)
                cursor.execute(f"DELETE FROM attachments WHERE note_id IN ({placeholders})", note_ids)
            else:
                cursor.execute(f"UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id IN ({placeholders})", [now] + note_ids)
            conn.commit()
        self._notify_change("notes-deleted", {"note_ids": note_ids, "permanent": permanent}, sender=sender)

    def restore_notes(self, note_ids: List[str], sender: Any = None):
        """Restore multiple notes from trash."""
        if not note_ids:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id IN ({placeholders})", [now] + note_ids)
            conn.commit()
        self._notify_change("notes-restored", {"note_ids": note_ids}, sender=sender)

    def toggle_pin_note(self, note_id: str, sender: Any = None) -> bool:
        """Toggle pinned status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                new_state = 0 if row["is_pinned"] else 1
                cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_state, time.time(), note_id))
                conn.commit()
                self._notify_change("note-pin-toggled", {"note_id": note_id, "is_pinned": bool(new_state)}, sender=sender)
                return bool(new_state)
        return False

    def duplicate_note(self, note_id: str) -> Optional[Note]:
        """Duplicate an existing note."""
        note = self.get_note(note_id)
        if not note:
            return None
        new_id = str(uuid.uuid4())
        dup = self.save_note(
            note_id=new_id,
            title=f"{note.title} (Copy)",
            category=note.category,
            content_html=note.content_html,
            content_markdown=note.content_markdown,
            tags=note.tags
        )
        # Duplicate attachments
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attachments WHERE note_id = ?", (note_id,))
            for att in cursor.fetchall():
                self.save_attachment(
                    note_id=new_id,
                    filename=att["filename"],
                    mime_type=att["mime_type"],
                    data=att["data"]
                )
        return dup

    # ── Attachments API ───────────────────────────────────────────────────

    def save_attachment(
        self,
        note_id: str,
        filename: str,
        mime_type: str,
        data: bytes,
        attachment_id: Optional[str] = None
    ) -> str:
        """Store image or file as a binary blob in the attachments table."""
        att_id = attachment_id or str(uuid.uuid4())
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO attachments (id, note_id, filename, mime_type, data, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (att_id, note_id, filename, mime_type, data, len(data), now))
            conn.commit()
        return att_id

    def get_attachment(self, attachment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve attachment binary data and metadata."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "note_id": row["note_id"],
                    "filename": row["filename"],
                    "mime_type": row["mime_type"],
                    "data": row["data"],
                    "size_bytes": row["size_bytes"],
                }
            return None

    def delete_attachment(self, attachment_id: str):
        """Delete specific attachment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()

    def _resolve_attachment_uri_to_bytes(self, cursor, url: str) -> Optional[bytes]:
        """Resolve an image URI to binary data within an existing DB cursor."""
        if not url:
            return None
        if url.startswith("attachment://") or url.startswith("attachment:"):
            prefix = "attachment://" if url.startswith("attachment://") else "attachment:"
            att_id = url[len(prefix):].split("/")[0].split("?")[0].split("#")[0]
            cursor.execute("SELECT data FROM attachments WHERE id = ? AND data IS NOT NULL", (att_id,))
            r = cursor.fetchone()
            if r and r["data"]:
                return r["data"]
            if "." in att_id:
                base_id = att_id.rsplit(".", 1)[0]
                cursor.execute("SELECT data FROM attachments WHERE id = ? AND data IS NOT NULL", (base_id,))
                r = cursor.fetchone()
                if r and r["data"]:
                    return r["data"]
        elif url.startswith("data:image/") and ";base64," in url:
            try:
                b64_part = url.split(";base64,", 1)[1]
                return base64.b64decode(b64_part)
            except Exception:
                pass
        elif url.startswith("file://") or (url.startswith("/") and os.path.isabs(url)):
            local_path = url[len("file://"):] if url.startswith("file://") else url
            local_path = urllib.parse.unquote(local_path)
            if os.path.isfile(local_path):
                try:
                    with open(local_path, "rb") as f:
                        return f.read()
                except Exception:
                    pass
        return None

    def get_note_first_image(self, note_id: str) -> Optional[bytes]:
        """Retrieve binary data for the top-most primary image of a note.
        
        If a note has multiple images, only the top-most (first in document order)
        image is returned; subsequent images are ignored.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. First check the note's content to find the top-most image in document order
            cursor.execute("SELECT content_markdown, content_html FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                content = row["content_markdown"] or row["content_html"] or ""
                if content:
                    matches = []
                    for m in re.finditer(r'!\[.*?\]\((.+?)\)', content):
                        raw_url = m.group(1).strip().split()[0]
                        if raw_url:
                            matches.append((m.start(), raw_url))
                    for m in re.finditer(r'<img\s+[^>]*?src=["\']([^"\']+)["\']', content, re.IGNORECASE):
                        raw_url = m.group(1).strip()
                        if raw_url:
                            matches.append((m.start(), raw_url))

                    matches.sort(key=lambda x: x[0])
                    for _, url in matches:
                        data = self._resolve_attachment_uri_to_bytes(cursor, url)
                        if data:
                            return data

            return None

    def get_note_first_table(self, note_id: str) -> Optional[List[List[str]]]:
        """Retrieve structured table rows for the first table of a note if present."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_markdown, content_html FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                content = row["content_markdown"] or row["content_html"] or ""
                if content and ("|" in content or "<table" in content.lower()):
                    return extract_table_data(content)
        return None

    def get_categories(self) -> List[Category]:
        """Fetch categories with active note counts in that category and its subcategories."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, icon, color FROM categories ORDER BY name ASC")
            cat_rows = cursor.fetchall()

            # Note counts per category including subcategories (without counting subcategories as notes)
            cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM notes "
                "WHERE is_trashed = 0 AND category != '' AND category IS NOT NULL "
                "GROUP BY category"
            )
            note_rows = cursor.fetchall()
            cat_counts: Dict[str, int] = {}
            for row in note_rows:
                cat = row["category"]
                cnt = row["cnt"]
                parts = cat.split("/")
                for i in range(len(parts)):
                    ancestor = "/".join(parts[:i + 1])
                    cat_counts[ancestor] = cat_counts.get(ancestor, 0) + cnt

            return [
                Category(
                    id=row["id"],
                    name=row["name"],
                    icon=row["icon"] or "folder-symbolic",
                    color=row["color"] or "",
                    count=cat_counts.get(row["name"], 0)
                )
                for row in cat_rows
            ]

    def create_category(self, name: str, icon: str = "folder-symbolic", color: str = "", sender: Any = None) -> bool:
        """Create a new category."""
        clean_name = name.strip()
        if not clean_name:
            return False
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO categories (id, name, icon, color, created_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), clean_name, icon, color, time.time())
                )
                conn.commit()
            self._notify_change("categories-updated", {"category": clean_name}, sender=sender)
            return True
        except sqlite3.IntegrityError:
            return False

    def rename_category(self, old_name: str, new_name: str, sender: Any = None):
        """Rename a category and all its subcategories and update affected notes."""
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name or old_name == new_name:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (new_name,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM categories WHERE name = ?", (old_name,))
            else:
                cursor.execute("UPDATE categories SET name = ? WHERE name = ?", (new_name, old_name))
            old_prefix = old_name + "/"
            new_prefix = new_name + "/"
            cursor.execute(
                "UPDATE categories SET name = ? || substr(name, ?) WHERE name LIKE ?",
                (new_prefix, len(old_prefix) + 1, old_prefix + "%")
            )
            cursor.execute("UPDATE notes SET category = ?, updated_at = ? WHERE category = ?", (new_name, now, old_name))
            cursor.execute(
                "UPDATE notes SET category = ? || substr(category, ?), updated_at = ? WHERE category LIKE ?",
                (new_prefix, len(old_prefix) + 1, now, old_prefix + "%")
            )
            conn.commit()
        self._notify_change("categories-updated", {"old_name": old_name, "new_name": new_name}, sender=sender)

    def delete_category(self, name: str, sender: Any = None):
        """Delete category and any subcategories and reset affected notes' category."""
        clean_name = name.strip()
        if not clean_name:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE name = ? OR name LIKE ?", (clean_name, clean_name + "/%"))
            cursor.execute(
                "UPDATE notes SET category = '', updated_at = ? WHERE category = ? OR category LIKE ?",
                (now, clean_name, clean_name + "/%")
            )
            conn.commit()
        self._notify_change("categories-updated", {"deleted": clean_name}, sender=sender)

    def get_counts(self) -> Dict[str, int]:
        """Return counts for standard tabs plus per-category counts in 2 fast queries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            recent_cutoff = time.time() - (7 * 86400)
            cursor.execute("""
            SELECT
                COUNT(CASE WHEN is_trashed = 0 THEN 1 END) as all_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_pinned = 1 THEN 1 END) as pinned_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND (has_todo = 1 OR has_todo_fn(content_markdown, content_html) = 1) THEN 1 END) as todo_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND has_list_fn(content_markdown, content_html) = 1 THEN 1 END) as list_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND updated_at >= ? THEN 1 END) as recent_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND (category = '' OR category IS NULL) THEN 1 END) as uncat_cnt,
                COUNT(CASE WHEN is_trashed = 1 THEN 1 END) as trash_cnt
            FROM notes
            """, (recent_cutoff,))
            counts_row = cursor.fetchone()
            all_cnt = counts_row["all_cnt"]
            pinned_cnt = counts_row["pinned_cnt"]
            todo_cnt = counts_row["todo_cnt"]
            list_cnt = counts_row["list_cnt"]
            recent_cnt = counts_row["recent_cnt"]
            uncat_cnt = counts_row["uncat_cnt"]
            trash_cnt = counts_row["trash_cnt"]

            cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM notes "
                "WHERE is_trashed = 0 AND category != '' AND category IS NOT NULL "
                "GROUP BY category"
            )
            cat_rows = cursor.fetchall()
            cat_counts: Dict[str, int] = {}
            for row in cat_rows:
                cat = row["category"]
                cnt = row["cnt"]
                parts = cat.split("/")
                for i in range(len(parts)):
                    ancestor = "/".join(parts[:i + 1])
                    cat_counts[f"cat:{ancestor}"] = cat_counts.get(f"cat:{ancestor}", 0) + cnt

            result = {
                "all": all_cnt,
                "pinned": pinned_cnt,
                "favorites": pinned_cnt,
                "todo": todo_cnt,
                "todos": todo_cnt,
                "list": list_cnt,
                "lists": list_cnt,
                "recent": recent_cnt,
                "uncategorized": uncat_cnt,
                "trash": trash_cnt,
            }
            result.update(cat_counts)
            for tag_name, cnt in self.get_all_tags():
                result[f"tag:{tag_name}"] = cnt
            return result

    def _create_category_sync(self, conn: sqlite3.Connection, full_name: str):
        """Helper to create category and missing ancestor categories within an existing transaction."""
        parts = full_name.split("/")
        now = time.time()
        for i in range(len(parts)):
            sub = "/".join(parts[:i + 1])
            conn.execute(
                "INSERT OR IGNORE INTO categories (id, name, created_at) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), sub, now)
            )

    def get_all_tags(self) -> List[Tuple[str, int]]:
        """Return list of (tag_name, count) for all tags in non-trashed notes, sorted by count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tags, content_markdown FROM notes WHERE is_trashed = 0"
            )
            tag_counts: Dict[str, int] = {}
            for r in cursor.fetchall():
                raw = r["tags"]
                t_list = []
                if raw:
                    try:
                        t_list = json.loads(raw)
                    except Exception:
                        t_list = [x.strip() for x in str(raw).split(",") if x.strip()]
                if not t_list and r["content_markdown"]:
                    t_list = extract_tags(r["content_markdown"])
                for t in t_list:
                    t_clean = t.strip().lstrip("#").lower()
                    if t_clean:
                        tag_counts[t_clean] = tag_counts.get(t_clean, 0) + 1
            return sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))

    def find_note_by_title(self, title: str) -> Optional[Note]:
        """Find non-trashed note by title (case-insensitive exact match)."""
        clean_title = title.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notes WHERE is_trashed = 0 AND LOWER(TRIM(title)) = LOWER(?) LIMIT 1",
                (clean_title,)
            )
            row = cursor.fetchone()
            if row:
                return Note.from_row(row)
            return None

    def get_all_note_titles(self) -> List[str]:
        """Return list of distinct note titles for internal link autocompletion."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT title FROM notes WHERE is_trashed = 0 AND title IS NOT NULL AND title != '' AND title != 'Untitled Note'"
            )
            return [r["title"] for r in cursor.fetchall()]

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row["value"] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except Exception as e:
            print("Error saving setting:", e)

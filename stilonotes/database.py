# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import sqlite3
import threading
import time
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
    check_has_todo,
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

        self._init_db()

    @contextmanager
    def get_connection(self):
        """Thread-safe context manager for persistent SQLite connection."""
        with self._lock:
            if self._conn is None:
                is_mem = str(self.db_path) == ":memory:"
                conn_path = ":memory:" if is_mem else str(self.db_path)
                conn = sqlite3.connect(conn_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row

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
            elif filter_type == "todo":
                query += " AND has_todo = 1"
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
                if has_todo is not None:
                    new_todo = 1 if has_todo else 0
                else:
                    new_todo = 1 if check_has_todo(new_md or new_html) else 0

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
                if has_todo is not None:
                    new_todo = 1 if has_todo else 0
                else:
                    new_todo = 1 if check_has_todo(new_md or new_html) else 0

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

            conn.commit()
            return Note(
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

    def create_note(self, title: str = "Untitled Note", category: str = "", initial_text: str = "") -> Note:
        """Create a new note."""
        note_id = str(uuid.uuid4())
        md_content = initial_text or (f"# {title}\n\n" if title != "Untitled Note" else "")
        html_content = markdown_to_html(md_content) if md_content else f"<h1>{title}</h1><div><br></div>"
        return self.save_note(
            note_id=note_id,
            title=title,
            category=category,
            content_html=html_content,
            content_markdown=md_content
        )

    def delete_note(self, note_id: str, permanent: bool = False):
        """Move note to trash, or delete permanently."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if permanent:
                cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))
            else:
                cursor.execute("UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()

    def restore_note(self, note_id: str):
        """Restore note from trash."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()

    def set_note_pinned(self, note_id: str, is_pinned: bool):
        """Set pinned status directly."""
        val = 1 if is_pinned else 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (val, time.time(), note_id))
            conn.commit()

    def set_notes_pinned(self, note_ids: List[str], is_pinned: bool):
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

    def set_note_category(self, note_id: str, category: str):
        """Set category for a single note."""
        clean_cat = category.strip()
        if clean_cat:
            self.create_category(clean_cat)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET category = ?, updated_at = ? WHERE id = ?", (clean_cat, time.time(), note_id))
            conn.commit()

    def set_notes_category(self, note_ids: List[str], category: str):
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

    def delete_notes(self, note_ids: List[str], permanent: bool = False):
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

    def restore_notes(self, note_ids: List[str]):
        """Restore multiple notes from trash."""
        if not note_ids:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id IN ({placeholders})", [now] + note_ids)
            conn.commit()

    def toggle_pin_note(self, note_id: str) -> bool:
        """Toggle pinned status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                new_state = 0 if row["is_pinned"] else 1
                cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_state, time.time(), note_id))
                conn.commit()
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

    def get_categories(self) -> List[Category]:
        """Fetch categories with active note counts in a single optimized query."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT c.id, c.name, c.icon, c.color,
                   COALESCE(n.cnt, 0) as count
            FROM categories c
            LEFT JOIN (
                SELECT category, COUNT(*) as cnt
                FROM notes
                WHERE is_trashed = 0 AND category != '' AND category IS NOT NULL
                GROUP BY category
            ) n ON c.name = n.category
            ORDER BY c.name ASC
            """)
            return [
                Category(
                    id=row["id"],
                    name=row["name"],
                    icon=row["icon"] or "folder-symbolic",
                    color=row["color"] or "",
                    count=row["count"]
                )
                for row in cursor.fetchall()
            ]

    def create_category(self, name: str, icon: str = "folder-symbolic", color: str = "") -> bool:
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
                return True
        except sqlite3.IntegrityError:
            return False

    def rename_category(self, old_name: str, new_name: str):
        """Rename a category and all its subcategories and update affected notes."""
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name or old_name == new_name:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
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

    def delete_category(self, name: str):
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

    def get_counts(self) -> Dict[str, int]:
        """Return counts for standard tabs plus per-category counts in 2 fast queries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT
                COUNT(CASE WHEN is_trashed = 0 THEN 1 END) as all_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_pinned = 1 THEN 1 END) as pinned_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND has_todo = 1 THEN 1 END) as todo_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND (category = '' OR category IS NULL) THEN 1 END) as uncat_cnt,
                COUNT(CASE WHEN is_trashed = 1 THEN 1 END) as trash_cnt
            FROM notes
            """)
            counts_row = cursor.fetchone()
            all_cnt = counts_row["all_cnt"]
            pinned_cnt = counts_row["pinned_cnt"]
            todo_cnt = counts_row["todo_cnt"]
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

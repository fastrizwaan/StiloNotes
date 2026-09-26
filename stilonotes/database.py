# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any
from gi.repository import GLib

from stilonotes.models import Note, Category
from stilonotes.markdown_utils import (
    extract_title_and_excerpt,
    extract_tags,
    check_has_todo,
    markdown_to_html,
    html_to_markdown,
)

class NoteDatabase:
    """SQLite Database manager for Stilo Notes."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            data_dir = Path(GLib.get_user_data_dir()) / "stilonotes"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "stilonotes.db"

        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Notes table
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

            # Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes (updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed ON notes (is_trashed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes (is_pinned)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_category ON notes (category)")

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
- **Fast Sidebar Organization**: Group notes by Categories, #tags, or Favorites.
- **Real-time Statistics**: View word count, characters, and reading time.
- **Export Anywhere**: Export cleanly to Markdown, HTML, or Plain Text.

### 📝 Try These Quick Formatting Shortcuts
- Type `# ` for Heading 1, `## ` for Heading 2, or `### ` for Heading 3
- Type `- [ ] ` to start an interactive checklist
- Type `* ` or `- ` for bullet lists, `1. ` for numbered lists
- Type `> ` for blockquotes
- Type `---` on an empty line for a divider
- Type `**bold**`, `*italic*`, `==highlight==`, or `~~strikethrough~~`
- Add `#stilo` or `#ideas` anywhere in your text to tag your notes!

### ☑️ Your First Checklist
- [x] Launch Stilo Notes
- [ ] Try typing a new thought below
- [ ] Toggle dark and light mode
- [ ] Create a custom category in the sidebar

Enjoy writing with Stilo Notes! #welcome #notes
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
        """Fetch notes with flexible filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM notes WHERE 1=1"
            params: List[Any] = []

            # Trash filtering
            if filter_type == "trash":
                query += " AND is_trashed = 1"
            else:
                query += " AND is_trashed = 0"

            # Category / Tab filters
            if filter_type == "pinned":
                query += " AND is_pinned = 1"
            elif filter_type == "todo":
                query += " AND has_todo = 1"
            elif filter_type == "category" and category_name:
                query += " AND category = ?"
                params.append(category_name)

            # Tag filter
            if tag_name:
                query += " AND tags LIKE ?"
                params.append(f"%{tag_name}%")

            # Search query
            if search_query:
                q = f"%{search_query.strip()}%"
                query += " AND (title LIKE ? OR excerpt LIKE ? OR content_markdown LIKE ? OR tags LIKE ?)"
                params.extend([q, q, q, q])

            # Pinned notes appear first, then sorted by updated_at descending
            query += " ORDER BY is_pinned DESC, updated_at DESC"

            cursor.execute(query, params)
            return [Note.from_row(row) for row in cursor.fetchall()]

    def get_note(self, note_id: str) -> Optional[Note]:
        """Retrieve single note by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            return Note.from_row(row) if row else None

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
    ) -> Note:
        """Create or update a note with automatic excerpt and tag computation."""
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()

            if row:
                existing = Note.from_row(row)
                new_html = content_html if content_html is not None else existing.content_html
                new_md = content_markdown if content_markdown is not None else (
                    html_to_markdown(new_html) if content_html is not None else existing.content_markdown
                )

                extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                new_title = title if (title is not None and title != "Untitled Note") else (
                    extracted_title or existing.title or "Untitled Note"
                )
                new_excerpt = excerpt if excerpt is not None else extracted_excerpt
                new_tags = tags if tags is not None else extract_tags(new_md or new_html)
                new_category = category if category is not None else existing.category
                new_pinned = int(is_pinned if is_pinned is not None else existing.is_pinned)
                new_archived = int(is_archived if is_archived is not None else existing.is_archived)
                new_trashed = int(is_trashed if is_trashed is not None else existing.is_trashed)
                new_todo = 1 if check_has_todo(new_html or new_md) else 0

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
                new_html = content_html or "<h1>Untitled Note</h1><div><br></div>"
                new_md = content_markdown or (html_to_markdown(new_html) if new_html else "")
                extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                new_title = title if (title and title != "Untitled Note") else (extracted_title or "Untitled Note")
                new_excerpt = excerpt if excerpt is not None else extracted_excerpt
                new_tags = tags if tags is not None else extract_tags(new_md or new_html)
                new_category = category or ""
                new_pinned = int(is_pinned or 0)
                new_archived = int(is_archived or 0)
                new_trashed = int(is_trashed or 0)
                new_todo = 1 if check_has_todo(new_html or new_md) else 0

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
            return self.get_note(note_id)

    def create_note(self, title: str = "Untitled Note", category: str = "", initial_text: str = "") -> Note:
        """Create a new note."""
        note_id = str(uuid.uuid4())
        html_content = markdown_to_html(initial_text) if initial_text else f"<h1>{title}</h1><div><br></div>"
        md_content = initial_text or (f"# {title}\n\n" if title != "Untitled Note" else "")
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
            else:
                cursor.execute("UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()

    def restore_note(self, note_id: str):
        """Restore note from trash."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id = ?", (time.time(), note_id))
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
        return self.save_note(
            note_id=new_id,
            title=f"{note.title} (Copy)",
            category=note.category,
            content_html=note.content_html,
            content_markdown=note.content_markdown,
            tags=note.tags
        )

    def get_categories(self) -> List[Category]:
        """Fetch categories with active note counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories ORDER BY name ASC")
            cats = []
            for row in cursor.fetchall():
                c_name = row["name"]
                cursor.execute("SELECT COUNT(*) as cnt FROM notes WHERE is_trashed = 0 AND category = ?", (c_name,))
                count = cursor.fetchone()["cnt"]
                cats.append(Category(
                    id=row["id"],
                    name=c_name,
                    icon=row["icon"] or "folder-symbolic",
                    color=row["color"] or "",
                    count=count
                ))
            return cats

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

    def delete_category(self, name: str):
        """Delete category and reset notes in that category."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
            cursor.execute("UPDATE notes SET category = '' WHERE category = ?", (name,))
            conn.commit()

    def get_counts(self) -> Dict[str, int]:
        """Return counts for standard tabs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM notes WHERE is_trashed = 0")
            all_cnt = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM notes WHERE is_trashed = 0 AND is_pinned = 1")
            pinned_cnt = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM notes WHERE is_trashed = 0 AND has_todo = 1")
            todo_cnt = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM notes WHERE is_trashed = 1")
            trash_cnt = cursor.fetchone()["cnt"]

            return {
                "all": all_cnt,
                "pinned": pinned_cnt,
                "todo": todo_cnt,
                "trash": trash_cnt
            }

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

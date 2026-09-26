# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class Note:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Note"
    content_html: str = ""
    content_markdown: str = ""
    excerpt: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    is_pinned: bool = False
    is_archived: bool = False
    is_trashed: bool = False
    has_todo: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content_html": self.content_html,
            "content_markdown": self.content_markdown,
            "excerpt": self.excerpt,
            "category": self.category,
            "tags": self.tags,
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            "is_trashed": self.is_trashed,
            "has_todo": self.has_todo,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "Note":
        tags_raw = row["tags"] if "tags" in row.keys() else "[]"
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

        category = row["category"] if "category" in row.keys() and row["category"] else ""

        return cls(
            id=str(row["id"]),
            title=row["title"] or "Untitled Note",
            content_html=row["content_html"] or "",
            content_markdown=row["content_markdown"] or "",
            excerpt=row["excerpt"] or "",
            category=category,
            tags=tags,
            is_pinned=bool(row["is_pinned"]),
            is_archived=bool(row["is_archived"]),
            is_trashed=bool(row["is_trashed"]),
            has_todo=bool(row["has_todo"]),
            created_at=float(row["created_at"] or time.time()),
            updated_at=float(row["updated_at"] or time.time()),
        )

@dataclass
class Category:
    id: str
    name: str
    icon: str = "folder-symbolic"
    color: str = ""
    count: int = 0
    is_system: bool = False

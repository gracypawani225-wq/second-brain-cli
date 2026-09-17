"""A small SQLite data layer for notes, tags, and full-text search."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3


DEFAULT_DB_PATH = Path.home() / ".second-brain" / "brain.db"


@dataclass(frozen=True)
class Note:
    id: int
    text: str
    created_at: datetime
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrainStats:
    total_notes: int
    notes_this_week: int
    most_used_tags: tuple[tuple[str, int], ...]
    oldest_note: Note | None
    newest_note: Note | None


class BrainDB:
    """Owns the local database connection and all persistence queries."""

    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        # SQLite leaves foreign-key enforcement off unless every connection opts in.
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL CHECK(length(trim(text)) > 0),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE
            );

            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (note_id, tag_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                text,
                content='notes',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, text) VALUES (new.id, new.text);
            END;

            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, text)
                VALUES ('delete', old.id, old.text);
            END;

            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE OF text ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, text)
                VALUES ('delete', old.id, old.text);
                INSERT INTO notes_fts(rowid, text) VALUES (new.id, new.text);
            END;
            """
        )
        self.connection.commit()

    @staticmethod
    def _normalise_tags(tags: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for tag in tags:
            value = tag.strip().lower()
            if value and value not in cleaned:
                cleaned.append(value)
        return tuple(cleaned)

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)

    def add_note(self, text: str, tags: list[str] | tuple[str, ...] = ()) -> Note:
        text = text.strip()
        if not text:
            raise ValueError("A note cannot be empty.")
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        cursor = self.connection.execute(
            "INSERT INTO notes(text, created_at) VALUES (?, ?)",
            (text, created_at.isoformat()),
        )
        note_id = int(cursor.lastrowid)
        normalised_tags = self._normalise_tags(tags)
        for tag in normalised_tags:
            self.connection.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
            self.connection.execute(
                """
                INSERT OR IGNORE INTO note_tags(note_id, tag_id)
                SELECT ?, id FROM tags WHERE name = ? COLLATE NOCASE
                """,
                (note_id, tag),
            )
        self.connection.commit()
        return Note(note_id, text, created_at, normalised_tags)

    def _tags_for(self, note_id: int) -> tuple[str, ...]:
        rows = self.connection.execute(
            """
            SELECT tags.name FROM tags
            JOIN note_tags ON note_tags.tag_id = tags.id
            WHERE note_tags.note_id = ?
            ORDER BY tags.name COLLATE NOCASE
            """,
            (note_id,),
        ).fetchall()
        return tuple(row["name"] for row in rows)

    def _note_from_row(self, row: sqlite3.Row) -> Note:
        return Note(
            id=row["id"],
            text=row["text"],
            created_at=self._parse_datetime(row["created_at"]),
            tags=self._tags_for(row["id"]),
        )

    def get_note(self, note_id: int) -> Note | None:
        row = self.connection.execute(
            "SELECT id, text, created_at FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        return self._note_from_row(row) if row else None

    def list_notes(self, tag: str | None = None) -> list[Note]:
        if tag:
            rows = self.connection.execute(
                """
                SELECT notes.id, notes.text, notes.created_at FROM notes
                JOIN note_tags ON note_tags.note_id = notes.id
                JOIN tags ON tags.id = note_tags.tag_id
                WHERE tags.name = ? COLLATE NOCASE
                ORDER BY notes.created_at DESC
                """,
                (tag.strip(),),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id, text, created_at FROM notes ORDER BY created_at DESC"
            ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def search_notes(self, query: str, limit: int = 8) -> list[Note]:
        # Quote individual terms so punctuation never becomes FTS syntax.
        terms = re.findall(r"[\w]+", query, flags=re.UNICODE)
        if not terms:
            return []
        fts_query = " AND ".join(f'"{term}"' for term in terms)
        rows = self.connection.execute(
            """
            SELECT notes.id, notes.text, notes.created_at
            FROM notes_fts
            JOIN notes ON notes.id = notes_fts.rowid
            WHERE notes_fts MATCH ?
            ORDER BY bm25(notes_fts)
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def delete_note(self, note_id: int) -> bool:
        cursor = self.connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def stats(self) -> BrainStats:
        total_notes = int(self.connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0])
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        notes_this_week = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM notes WHERE created_at >= ?", (week_ago,)
            ).fetchone()[0]
        )
        tag_rows = self.connection.execute(
            """
            SELECT tags.name, COUNT(note_tags.note_id) AS usage_count
            FROM tags JOIN note_tags ON note_tags.tag_id = tags.id
            GROUP BY tags.id
            ORDER BY usage_count DESC, tags.name COLLATE NOCASE
            LIMIT 5
            """
        ).fetchall()
        oldest_row = self.connection.execute(
            "SELECT id, text, created_at FROM notes ORDER BY created_at ASC, id ASC LIMIT 1"
        ).fetchone()
        newest_row = self.connection.execute(
            "SELECT id, text, created_at FROM notes ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return BrainStats(
            total_notes=total_notes,
            notes_this_week=notes_this_week,
            most_used_tags=tuple((row["name"], row["usage_count"]) for row in tag_rows),
            oldest_note=self._note_from_row(oldest_row) if oldest_row else None,
            newest_note=self._note_from_row(newest_row) if newest_row else None,
        )

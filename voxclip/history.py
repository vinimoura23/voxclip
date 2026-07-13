"""History management using SQLite."""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """A single transcription history entry."""
    id: int
    text: str
    language: str
    confidence: float
    duration_seconds: float
    created_at: str  # ISO format

    @property
    def created_datetime(self) -> datetime:
        return datetime.fromisoformat(self.created_at)

    @property
    def preview(self) -> str:
        """Short preview of the text (first 80 chars)."""
        if len(self.text) <= 80:
            return self.text
        return self.text[:77] + "..."


class HistoryManager:
    """Manages transcription history in SQLite."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'auto',
        confidence REAL NOT NULL DEFAULT 0.0,
        duration_seconds REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at DESC);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
        log.info("History database ready at %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def add(
        self,
        text: str,
        language: str = "auto",
        confidence: float = 0.0,
        duration_seconds: float = 0.0,
    ) -> int:
        """Add a new transcription to history. Returns the entry ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO history (text, language, confidence, duration_seconds)
                   VALUES (?, ?, ?, ?)""",
                (text, language, confidence, duration_seconds),
            )
            entry_id = cursor.lastrowid
            log.info("Added history entry #%d (%d chars, lang=%s)", entry_id, len(text), language)
            return entry_id

    def get_recent(self, limit: int = 50) -> list[HistoryEntry]:
        """Get the most recent entries."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_by_id(self, entry_id: int) -> Optional[HistoryEntry]:
        """Get a specific entry by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ?", (entry_id,)
            ).fetchone()
            return self._row_to_entry(row) if row else None

    def search(self, query: str, limit: int = 50) -> list[HistoryEntry]:
        """Search history by text content."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM history
                   WHERE text LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def delete(self, entry_id: int) -> bool:
        """Delete a specific entry."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    def clear(self) -> int:
        """Clear all history. Returns number of entries deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history")
            count = cursor.rowcount
            log.info("Cleared %d history entries", count)
            return count

    def count(self) -> int:
        """Get total number of entries."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM history").fetchone()
            return row[0]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            text=row["text"],
            language=row["language"],
            confidence=row["confidence"],
            duration_seconds=row["duration_seconds"],
            created_at=row["created_at"],
        )

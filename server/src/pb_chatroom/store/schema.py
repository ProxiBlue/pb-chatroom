"""SQLite schema bootstrap for pb-chatroom."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

_DDL = """
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open', 'acked')),
    created_at TEXT NOT NULL,
    last_message_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    from_participant TEXT NOT NULL,
    to_participant TEXT NOT NULL,
    body TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('message', 'ack')),
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread_created
    ON messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_threads_to_status
    ON threads(status, last_message_at DESC);
"""


@asynccontextmanager
async def connect(db_path: Path | str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('PRAGMA foreign_keys = ON')
        await db.execute('PRAGMA journal_mode = WAL')
        yield db


async def init_schema(db_path: Path | str) -> None:
    async with connect(db_path) as db:
        await db.executescript(_DDL)
        await db.commit()
    await init_schema_v0_4(db_path)


async def init_schema_v0_4(db_path: Path | str) -> None:
    """Apply v0.4.0 schema changes idempotently."""
    async with connect(db_path) as db:
        # Ensure base tables exist first (safe on fresh DB)
        await db.executescript(_DDL)

        # Helper: fetch existing column names for a table
        async def _col_names(table: str) -> set[str]:
            cur = await db.execute(f'PRAGMA table_info({table})')
            rows = await cur.fetchall()
            return {row[1] for row in rows}

        thread_cols = await _col_names('threads')

        for col, coltype in [
            ('discussion_type', 'TEXT'),
            ('claimed_by', 'TEXT'),
            ('claimed_at', 'TEXT'),
            ('claim_scope', 'TEXT'),
        ]:
            if col not in thread_cols:
                await db.execute(f'ALTER TABLE threads ADD COLUMN {col} {coltype}')

        await db.execute("""
            CREATE TABLE IF NOT EXISTS thread_recipients (
                thread_id    TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
                participant_id TEXT NOT NULL,
                acked_at     TEXT,
                PRIMARY KEY (thread_id, participant_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
        """)

        cur = await db.execute('SELECT version FROM schema_version')
        row = await cur.fetchone()
        if row is None:
            await db.execute('INSERT INTO schema_version (version) VALUES (4)')
        elif row[0] < 4:
            await db.execute('UPDATE schema_version SET version = 4')

        await db.commit()

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

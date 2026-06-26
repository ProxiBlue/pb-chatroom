"""Tests for SQLite schema bootstrap (Task 003)."""

from __future__ import annotations

import aiosqlite
import pytest

from pb_chatroom.store import connect, init_schema


async def _table_names(db_path) -> set[str]:
    async with connect(db_path) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def _pragma(db_path, pragma: str) -> str:
    async with connect(db_path) as db:
        cursor = await db.execute(f'PRAGMA {pragma}')
        row = await cursor.fetchone()
        return row[0] if row else ''


@pytest.mark.asyncio
async def test_it_creates_the_threads_and_messages_tables_when_init_schema_runs_on_a_fresh_db(
    sqlite_path,
):
    await init_schema(sqlite_path)
    tables = await _table_names(sqlite_path)
    assert 'threads' in tables
    assert 'messages' in tables


@pytest.mark.asyncio
async def test_it_is_idempotent_running_init_schema_twice_does_not_error(sqlite_path):
    await init_schema(sqlite_path)
    await init_schema(sqlite_path)


@pytest.mark.asyncio
async def test_it_enables_foreign_keys_pragma_on_new_connections(sqlite_path):
    await init_schema(sqlite_path)
    value = await _pragma(sqlite_path, 'foreign_keys')
    assert value == 1


@pytest.mark.asyncio
async def test_it_sets_journal_mode_to_wal_on_new_connections(sqlite_path):
    await init_schema(sqlite_path)
    value = await _pragma(sqlite_path, 'journal_mode')
    assert value == 'wal'


@pytest.mark.asyncio
async def test_it_rejects_a_thread_row_with_status_outside_the_open_acked_check_constraint(
    sqlite_path,
):
    await init_schema(sqlite_path)
    with pytest.raises(aiosqlite.IntegrityError):
        async with connect(sqlite_path) as db:
            await db.execute(
                'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at)'
                ' VALUES (?,?,?,?,?,?)',
                ('t1', 'subject', 'alice', 'invalid', '2024-01-01T00:00:00', '2024-01-01T00:00:00'),
            )
            await db.commit()


@pytest.mark.asyncio
async def test_it_cascade_deletes_messages_when_their_parent_thread_is_deleted(sqlite_path):
    await init_schema(sqlite_path)
    async with connect(sqlite_path) as db:
        await db.execute(
            'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at)'
            ' VALUES (?,?,?,?,?,?)',
            ('t1', 'subject', 'alice', 'open', '2024-01-01T00:00:00', '2024-01-01T00:00:00'),
        )
        await db.execute(
            'INSERT INTO messages (id, thread_id, from_participant, to_participant,'
            ' body, kind, metadata, created_at) VALUES (?,?,?,?,?,?,?,?)',
            ('m1', 't1', 'alice', 'bob', 'hello', 'message', '{}', '2024-01-01T00:00:01'),
        )
        await db.commit()

    async with connect(sqlite_path) as db:
        await db.execute('DELETE FROM threads WHERE id = ?', ('t1',))
        await db.commit()
        cursor = await db.execute('SELECT COUNT(*) FROM messages WHERE thread_id = ?', ('t1',))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 0

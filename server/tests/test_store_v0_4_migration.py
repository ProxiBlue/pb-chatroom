"""Tests for v0.4.0 schema migration (Task 002)."""

from __future__ import annotations

import pytest

from pb_chatroom.store import connect, init_schema
from pb_chatroom.store.schema import init_schema_v0_4


async def _columns(db_path, table: str) -> set[str]:
    async with connect(db_path) as db:
        cursor = await db.execute(f'PRAGMA table_info({table})')
        rows = await cursor.fetchall()
        return {row[1] for row in rows}


async def _table_names(db_path) -> set[str]:
    async with connect(db_path) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def _schema_version(db_path) -> int | None:
    async with connect(db_path) as db:
        cursor = await db.execute('SELECT version FROM schema_version')
        row = await cursor.fetchone()
        return row[0] if row else None


@pytest.mark.asyncio
async def test_it_applies_the_v0_4_0_migration_on_a_fresh_database(sqlite_path):
    await init_schema_v0_4(sqlite_path)
    tables = await _table_names(sqlite_path)
    assert 'threads' in tables
    assert 'messages' in tables
    assert 'thread_recipients' in tables
    assert 'schema_version' in tables


@pytest.mark.asyncio
async def test_it_applies_the_v0_4_0_migration_on_a_populated_v0_3_database_without_data_loss(
    sqlite_path,
):
    # bootstrap schema then insert rows using named columns (future-proof)
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

    await init_schema_v0_4(sqlite_path)

    async with connect(sqlite_path) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM threads')
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1

        cursor = await db.execute('SELECT COUNT(*) FROM messages')
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1


@pytest.mark.asyncio
async def test_it_adds_discussion_type_claimed_by_claimed_at_claim_scope_columns_to_threads(
    sqlite_path,
):
    await init_schema_v0_4(sqlite_path)
    cols = await _columns(sqlite_path, 'threads')
    assert 'discussion_type' in cols
    assert 'claimed_by' in cols
    assert 'claimed_at' in cols
    assert 'claim_scope' in cols


@pytest.mark.asyncio
async def test_it_creates_the_thread_recipients_table_with_thread_id_participant_id_acked_at_columns(  # noqa: E501
    sqlite_path,
):
    await init_schema_v0_4(sqlite_path)
    cols = await _columns(sqlite_path, 'thread_recipients')
    assert 'thread_id' in cols
    assert 'participant_id' in cols
    assert 'acked_at' in cols


@pytest.mark.asyncio
async def test_it_is_idempotent_when_init_schema_is_called_twice(sqlite_path):
    await init_schema(sqlite_path)
    await init_schema(sqlite_path)
    # must not raise


@pytest.mark.asyncio
async def test_it_preserves_existing_thread_rows_after_migration(sqlite_path):
    await init_schema(sqlite_path)
    async with connect(sqlite_path) as db:
        await db.execute(
            'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at)'
            ' VALUES (?,?,?,?,?,?)',
            ('t2', 'keep me', 'bob', 'open', '2024-02-01T00:00:00', '2024-02-01T00:00:00'),
        )
        await db.commit()

    await init_schema_v0_4(sqlite_path)

    async with connect(sqlite_path) as db:
        cursor = await db.execute('SELECT subject FROM threads WHERE id = ?', ('t2',))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 'keep me'


@pytest.mark.asyncio
async def test_it_stores_and_retrieves_schema_version_4_after_migration(sqlite_path):
    await init_schema_v0_4(sqlite_path)
    version = await _schema_version(sqlite_path)
    assert version == 4

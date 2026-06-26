"""Tests for threads store CRUD + filtering."""

from __future__ import annotations

import asyncio
import uuid as _uuid
from datetime import UTC, datetime

import pytest

from pb_chatroom.store import connect, init_schema
from pb_chatroom.store.threads import (
    create_thread,
    get_thread,
    get_thread_with_messages,
    list_threads,
    update_thread_status,
)


@pytest.fixture
async def db(sqlite_path):
    await init_schema(sqlite_path)
    return sqlite_path


async def test_it_creates_a_new_thread_with_generated_uuid_and_returns_the_row(db):
    row = await create_thread(
        db,
        subject='Hello world',
        created_by='agent-a',
        to_participant='agent-b',
        body='Hello world',
    )
    assert row['id']
    assert len(row['id']) == 36  # UUID4 string
    assert row['subject'] == 'Hello world'
    assert row['created_by'] == 'agent-a'
    assert row['status'] == 'open'
    assert row['created_at'].endswith('Z')
    assert row['last_message_at'].endswith('Z')


async def test_it_writes_the_seed_message_in_the_same_transaction_as_the_thread(db):
    row = await create_thread(
        db,
        subject='Seed msg test',
        created_by='agent-a',
        to_participant='agent-b',
        body='Initial body',
    )
    thread_id = row['id']
    async with connect(db) as conn:
        cursor = await conn.execute(
            'SELECT id, thread_id, from_participant, to_participant, body, kind'
            ' FROM messages WHERE thread_id = ?',
            (thread_id,),
        )
        messages = await cursor.fetchall()
    assert len(messages) == 1
    msg = messages[0]
    assert msg[1] == thread_id
    assert msg[2] == 'agent-a'
    assert msg[3] == 'agent-b'
    assert msg[4] == 'Initial body'
    assert msg[5] == 'message'


async def test_it_lists_all_threads_sorted_by_last_message_at_descending(db):
    r1 = await create_thread(
        db, subject='First', created_by='agent-a', to_participant='agent-b', body='First'
    )
    await asyncio.sleep(0.01)
    r2 = await create_thread(
        db, subject='Second', created_by='agent-a', to_participant='agent-b', body='Second'
    )
    rows = await list_threads(db)
    assert len(rows) == 2
    assert rows[0]['id'] == r2['id']  # newest first
    assert rows[1]['id'] == r1['id']


async def test_it_filters_list_threads_by_to_participant(db):
    await create_thread(
        db, subject='For B', created_by='agent-a', to_participant='agent-b', body='For B'
    )
    await create_thread(
        db, subject='For C', created_by='agent-a', to_participant='agent-c', body='For C'
    )
    rows = await list_threads(db, to_participant='agent-b')
    assert len(rows) == 1
    assert rows[0]['subject'] == 'For B'


async def test_it_filters_list_threads_by_status_open_or_acked(db):
    r1 = await create_thread(
        db, subject='Open thread', created_by='agent-a', to_participant='agent-b', body='Open'
    )
    r2 = await create_thread(
        db, subject='Acked thread', created_by='agent-a', to_participant='agent-b', body='Acked'
    )
    async with connect(db) as conn:
        await conn.execute("UPDATE threads SET status = 'acked' WHERE id = ?", (r2['id'],))
        await conn.commit()

    open_rows = await list_threads(db, status='open')
    acked_rows = await list_threads(db, status='acked')
    assert len(open_rows) == 1
    assert open_rows[0]['id'] == r1['id']
    assert len(acked_rows) == 1
    assert acked_rows[0]['id'] == r2['id']


async def test_it_returns_none_from_get_thread_for_unknown_id(db):
    result = await get_thread(db, 'nonexistent-id')
    assert result is None


async def test_it_returns_the_thread_with_messages_ordered_oldest_first_from_get_thread_with_messages(  # noqa: E501
    db,
):
    row = await create_thread(
        db, subject='With msgs', created_by='agent-a', to_participant='agent-b', body='Seed'
    )
    thread_id = row['id']
    later = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    async with connect(db) as conn:
        await conn.execute(
            """
            INSERT INTO messages (id, thread_id, from_participant, to_participant,
                                  body, kind, metadata, created_at)
            VALUES (?, ?, 'agent-b', 'agent-a', 'Reply', 'message', '{}', ?)
            """,
            (str(_uuid.uuid4()), thread_id, later),
        )
        await conn.commit()

    result = await get_thread_with_messages(db, thread_id)
    assert result is not None
    assert result['id'] == thread_id
    assert 'messages' in result
    assert len(result['messages']) == 2
    assert result['messages'][0]['body'] == 'Seed'
    assert result['messages'][1]['body'] == 'Reply'
    assert result['messages'][0]['created_at'] <= result['messages'][1]['created_at']


async def test_it_updates_thread_status_from_open_to_acked(db):
    row = await create_thread(
        db, subject='Status test', created_by='agent-a', to_participant='agent-b', body='Hi'
    )
    thread_id = row['id']
    assert row['status'] == 'open'
    await update_thread_status(db, thread_id, 'acked')
    updated = await get_thread(db, thread_id)
    assert updated is not None
    assert updated['status'] == 'acked'

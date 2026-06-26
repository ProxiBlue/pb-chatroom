"""Tests for messages store layer."""

from __future__ import annotations

import pytest

from pb_chatroom.store import connect, init_schema
from pb_chatroom.store.errors import ThreadNotFoundError
from pb_chatroom.store.messages import append_ack, append_message, list_messages


async def _seed_thread(
    db_path,
    thread_id='t1',
    subject='Test',
    created_by='alice',
    status='open',
    created_at='2024-01-01T00:00:00',
    last_message_at='2024-01-01T00:00:00',
):
    """Insert a thread row directly for test setup."""
    async with connect(db_path) as db:
        await db.execute(
            'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (thread_id, subject, created_by, status, created_at, last_message_at),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_it_appends_a_message_and_updates_the_parent_thread_last_message_at(sqlite_path):
    await init_schema(sqlite_path)
    await _seed_thread(sqlite_path, last_message_at='2024-01-01T00:00:00')

    row = await append_message(
        sqlite_path,
        thread_id='t1',
        from_participant='alice',
        to_participant='bob',
        body='Hello',
    )

    # returned row is a dict with expected fields
    assert row['thread_id'] == 't1'
    assert row['body'] == 'Hello'
    assert row['kind'] == 'message'

    # thread.last_message_at updated to match message created_at
    async with connect(sqlite_path) as db:
        db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        async with db.execute('SELECT last_message_at FROM threads WHERE id = ?', ('t1',)) as cur:
            thread = await cur.fetchone()
    assert thread['last_message_at'] == row['created_at']
    assert thread['last_message_at'] != '2024-01-01T00:00:00'


@pytest.mark.asyncio
async def test_it_raises_ThreadNotFoundError_when_appending_a_message_to_a_missing_thread(sqlite_path):  # noqa: E501
    await init_schema(sqlite_path)

    with pytest.raises(ThreadNotFoundError):
        await append_message(
            sqlite_path,
            thread_id='no-such-thread',
            from_participant='alice',
            to_participant='bob',
            body='Hello',
        )


@pytest.mark.asyncio
async def test_it_appends_an_ack_and_flips_the_parent_thread_status_to_acked(sqlite_path):
    await init_schema(sqlite_path)
    await _seed_thread(sqlite_path, status='open')

    row = await append_ack(
        sqlite_path,
        thread_id='t1',
        from_participant='bob',
        to_participant='alice',
    )

    assert row['kind'] == 'ack'

    async with connect(sqlite_path) as db:
        db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        async with db.execute('SELECT status FROM threads WHERE id = ?', ('t1',)) as cur:
            thread = await cur.fetchone()
    assert thread['status'] == 'acked'


@pytest.mark.asyncio
async def test_it_preserves_the_from_participant_and_to_participant_fields_verbatim(sqlite_path):
    await init_schema(sqlite_path)
    await _seed_thread(sqlite_path)

    row = await append_message(
        sqlite_path,
        thread_id='t1',
        from_participant='alice@example.com',
        to_participant='bob@example.com',
        body='Hi',
    )

    assert row['from_participant'] == 'alice@example.com'
    assert row['to_participant'] == 'bob@example.com'


@pytest.mark.asyncio
async def test_it_stores_metadata_as_JSON_text_and_round_trips_a_dict_through_list_messages(sqlite_path):  # noqa: E501
    await init_schema(sqlite_path)
    await _seed_thread(sqlite_path)

    meta = {'key': 'value', 'num': 42}
    await append_message(
        sqlite_path,
        thread_id='t1',
        from_participant='alice',
        to_participant='bob',
        body='With meta',
        metadata=meta,
    )

    msgs = await list_messages(sqlite_path, 't1')
    assert len(msgs) == 1
    assert msgs[0]['metadata'] == meta


@pytest.mark.asyncio
async def test_it_lists_messages_oldest_first_by_created_at(sqlite_path):
    await init_schema(sqlite_path)
    await _seed_thread(sqlite_path)

    r1 = await append_message(sqlite_path, thread_id='t1', from_participant='alice',
                              to_participant='bob', body='First')
    r2 = await append_message(sqlite_path, thread_id='t1', from_participant='bob',
                              to_participant='alice', body='Second')

    msgs = await list_messages(sqlite_path, 't1')
    assert len(msgs) == 2
    assert msgs[0]['id'] == r1['id']
    assert msgs[1]['id'] == r2['id']
    assert msgs[0]['created_at'] <= msgs[1]['created_at']

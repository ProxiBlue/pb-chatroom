"""Tests for Task 003: discussion_type, claim state, multi-recipient."""

from __future__ import annotations

import pytest

from pb_chatroom.store import init_schema


@pytest.fixture
async def db(sqlite_path):
    await init_schema(sqlite_path)
    return sqlite_path


async def _make_thread(db, thread_id: str = 't1', created_by: str = 'alice') -> None:
    from pb_chatroom.store.schema import connect

    async with connect(db) as conn:
        await conn.execute(
            'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at)'
            ' VALUES (?,?,?,?,?,?)',
            (
                thread_id,
                'test subject',
                created_by,
                'open',
                '2024-01-01T00:00:00Z',
                '2024-01-01T00:00:00Z',
            ),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_it_sets_discussion_type_on_a_thread_and_reads_it_back(db):
    from pb_chatroom.store.threads import get_thread, set_discussion_type

    await _make_thread(db)
    await set_discussion_type(db, 't1', 'task')
    thread = await get_thread(db, 't1')
    assert thread is not None
    assert thread['discussion_type'] == 'task'


@pytest.mark.asyncio
async def test_it_records_a_claim_returning_the_claimer_when_first_to_attempt(db):
    from pb_chatroom.store.threads import set_claim

    await _make_thread(db)
    result = await set_claim(db, 't1', participant_id='bob', scope='exclusive')
    assert result['claimed_by'] == 'bob'
    assert result['claim_scope'] == 'exclusive'
    assert result['claimed_at'] is not None


@pytest.mark.asyncio
async def test_it_rejects_a_second_claim_attempt_by_a_different_participant(db):
    from pb_chatroom.store.errors import ClaimConflictError
    from pb_chatroom.store.threads import set_claim

    await _make_thread(db)
    await set_claim(db, 't1', participant_id='bob', scope='exclusive')

    with pytest.raises(ClaimConflictError) as exc_info:
        await set_claim(db, 't1', participant_id='carol', scope='exclusive')

    assert exc_info.value.claimed_by == 'bob'


@pytest.mark.asyncio
async def test_it_returns_idempotent_success_when_the_same_participant_claims_twice(db):
    from pb_chatroom.store.threads import set_claim

    await _make_thread(db)
    first = await set_claim(db, 't1', participant_id='bob', scope='exclusive')
    second = await set_claim(db, 't1', participant_id='bob', scope='exclusive')
    assert second['claimed_by'] == 'bob'
    assert second['claimed_at'] == first['claimed_at']


@pytest.mark.asyncio
async def test_it_adds_and_lists_recipients_on_a_thread(db):
    from pb_chatroom.store.recipients import add_recipient, list_recipients

    await _make_thread(db)
    await add_recipient(db, 't1', participant_id='alice')
    await add_recipient(db, 't1', participant_id='bob')
    recipients = await list_recipients(db, 't1')
    ids = [r['participant_id'] for r in recipients]
    assert 'alice' in ids
    assert 'bob' in ids


@pytest.mark.asyncio
async def test_it_marks_a_single_recipient_acked_without_acking_the_thread(db):
    from pb_chatroom.store.recipients import (
        add_recipient,
        all_recipients_acked,
        mark_recipient_acked,
    )

    await _make_thread(db)
    await add_recipient(db, 't1', participant_id='alice')
    await add_recipient(db, 't1', participant_id='bob')
    await mark_recipient_acked(db, 't1', participant_id='alice')
    assert not await all_recipients_acked(db, 't1')


@pytest.mark.asyncio
async def test_it_reports_all_recipients_acked_true_only_when_every_recipient_has_acked(db):
    from pb_chatroom.store.recipients import (
        add_recipient,
        all_recipients_acked,
        mark_recipient_acked,
    )

    await _make_thread(db)
    await add_recipient(db, 't1', participant_id='alice')
    await add_recipient(db, 't1', participant_id='bob')
    await mark_recipient_acked(db, 't1', participant_id='alice')
    await mark_recipient_acked(db, 't1', participant_id='bob')
    assert await all_recipients_acked(db, 't1')

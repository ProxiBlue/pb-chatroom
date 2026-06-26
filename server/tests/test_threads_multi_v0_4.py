"""Tests for REST list/get/ack/post-message multi-recipient awareness (Task 005)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def test_app(sqlite_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.settings import Settings
    from pb_chatroom.store import init_schema

    await init_schema(sqlite_path)
    return create_app(Settings(db_path=sqlite_path))


@pytest.fixture
async def client(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url='http://test') as c:
        yield c


async def _create_thread(client, *, from_p, to_p, subject='test', body='hello'):
    """Helper: create single-recipient thread, return response JSON."""
    resp = await client.post(
        '/api/threads',
        json={'to': to_p, 'subject': subject, 'body': body},
        headers={'X-PB-Chatroom-Participant': from_p},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_multi_thread(client, *, from_p, to_participants, subject='test', body='hello'):
    """Helper: create multi-recipient thread, return response JSON."""
    resp = await client.post(
        '/api/threads',
        json={'to_participants': to_participants, 'subject': subject, 'body': body},
        headers={'X-PB-Chatroom-Participant': from_p},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_it_returns_a_thread_to_a_query_matching_the_primary_recipient(client):
    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b', subject='primary recip')
    thread_id = thread['id']

    resp = await client.get('/api/threads', params={'to': 'agent-b'})
    assert resp.status_code == 200
    ids = [t['id'] for t in resp.json()]
    assert thread_id in ids


async def test_it_returns_a_thread_to_a_query_matching_any_thread_recipients_entry(
    client, sqlite_path
):
    from pb_chatroom.store.recipients import add_recipient

    thread = await _create_thread(
        client, from_p='agent-a', to_p='agent-b', subject='multi recip query'
    )
    thread_id = thread['id']
    # Manually add agent-c as an additional recipient
    await add_recipient(sqlite_path, thread_id, participant_id='agent-c')

    resp = await client.get('/api/threads', params={'to': 'agent-c'})
    assert resp.status_code == 200
    ids = [t['id'] for t in resp.json()]
    assert thread_id in ids


async def test_it_sets_discussion_type_on_the_parent_thread_when_post_message_includes_it(
    client, sqlite_path
):
    from pb_chatroom.store.threads import get_thread

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']

    resp = await client.post(
        f'/api/threads/{thread_id}/messages',
        json={'body': 'follow up', 'discussion_type': 'design_question'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert resp.status_code == 201

    stored = await get_thread(sqlite_path, thread_id)
    assert stored['discussion_type'] == 'design_question'


async def test_it_does_not_overwrite_discussion_type_when_post_message_omits_it(
    client, sqlite_path
):
    from pb_chatroom.store.threads import get_thread, set_discussion_type

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']
    await set_discussion_type(sqlite_path, thread_id, 'bug_report')

    resp = await client.post(
        f'/api/threads/{thread_id}/messages',
        json={'body': 'reply without type'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert resp.status_code == 201

    stored = await get_thread(sqlite_path, thread_id)
    assert stored['discussion_type'] == 'bug_report'


async def test_it_marks_the_calling_recipient_as_acked_when_post_ack_is_called(
    client, sqlite_path
):
    from pb_chatroom.store.recipients import add_recipient, list_recipients

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']
    await add_recipient(sqlite_path, thread_id, participant_id='agent-c')

    resp = await client.post(
        f'/api/threads/{thread_id}/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-c'},
    )
    assert resp.status_code == 200

    recipients = await list_recipients(sqlite_path, thread_id)
    agent_c_row = next(r for r in recipients if r['participant_id'] == 'agent-c')
    assert agent_c_row['acked_at'] is not None


async def test_it_leaves_thread_status_open_when_only_one_of_multiple_recipients_has_acked(
    client, sqlite_path
):
    from pb_chatroom.store.recipients import add_recipient
    from pb_chatroom.store.threads import get_thread

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']
    # Add agent-c as secondary recipient (agent-b is primary in messages)
    await add_recipient(sqlite_path, thread_id, participant_id='agent-c')

    # agent-c acks but agent-b has not
    resp = await client.post(
        f'/api/threads/{thread_id}/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-c'},
    )
    assert resp.status_code == 200

    stored = await get_thread(sqlite_path, thread_id)
    assert stored['status'] == 'open'


async def test_it_flips_thread_status_to_acked_when_the_last_recipient_acks(
    client, sqlite_path
):
    from pb_chatroom.store.recipients import add_recipient
    from pb_chatroom.store.threads import get_thread

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']
    await add_recipient(sqlite_path, thread_id, participant_id='agent-b')
    await add_recipient(sqlite_path, thread_id, participant_id='agent-c')

    # agent-c acks first
    await client.post(
        f'/api/threads/{thread_id}/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-c'},
    )

    # agent-b acks last — should flip status
    resp = await client.post(
        f'/api/threads/{thread_id}/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert resp.status_code == 200

    stored = await get_thread(sqlite_path, thread_id)
    assert stored['status'] == 'acked'


async def test_it_returns_discussion_type_claimed_by_claimed_at_claim_scope_and_recipients_on_get_thread(  # noqa: E501
    client, sqlite_path
):
    from pb_chatroom.store.recipients import add_recipient
    from pb_chatroom.store.threads import set_claim, set_discussion_type

    thread = await _create_thread(client, from_p='agent-a', to_p='agent-b')
    thread_id = thread['id']
    await set_discussion_type(sqlite_path, thread_id, 'design_question')
    await set_claim(sqlite_path, thread_id, participant_id='agent-b', scope='implementation')
    await add_recipient(sqlite_path, thread_id, participant_id='agent-c')

    resp = await client.get(f'/api/threads/{thread_id}')
    assert resp.status_code == 200
    data = resp.json()

    assert data['discussion_type'] == 'design_question'
    assert data['claimed_by'] == 'agent-b'
    assert data['claimed_at'] is not None
    assert data['claim_scope'] == 'implementation'
    assert 'agent-c' in data['recipients']

"""Tests for POST /api/threads multi-recipient + discussion_type (Task 004)."""

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


async def test_it_creates_a_thread_with_a_single_to_participant_for_back_compat(client):
    response = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'back-compat', 'body': 'hello'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 201
    data = response.json()
    assert data['subject'] == 'back-compat'
    assert data['created_by'] == 'agent-a'
    assert data['status'] == 'open'
    assert 'id' in data


async def test_it_creates_a_thread_with_to_participants_and_inserts_all_recipients(
    client, sqlite_path
):
    from pb_chatroom.store.recipients import list_recipients

    response = await client.post(
        '/api/threads',
        json={
            'to_participants': ['agent-b', 'agent-c', 'agent-d'],
            'subject': 'multi-recip',
            'body': 'hello all',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 201
    data = response.json()
    thread_id = data['id']

    recipients = await list_recipients(sqlite_path, thread_id)
    participant_ids = {r['participant_id'] for r in recipients}
    assert 'agent-b' in participant_ids
    assert 'agent-c' in participant_ids
    assert 'agent-d' in participant_ids


async def test_it_accepts_a_discussion_type_field_and_persists_it_on_the_thread(
    client, sqlite_path
):
    from pb_chatroom.store.threads import get_thread

    response = await client.post(
        '/api/threads',
        json={
            'to': 'agent-b',
            'subject': 'design question',
            'body': 'what approach?',
            'discussion_type': 'design_question',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 201
    data = response.json()
    thread_id = data['id']

    thread = await get_thread(sqlite_path, thread_id)
    assert thread['discussion_type'] == 'design_question'


async def test_it_rejects_requests_with_both_empty_to_participant_and_empty_to_participants(client):
    response = await client.post(
        '/api/threads',
        json={'subject': 'no recipient', 'body': 'hello'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 422


async def test_it_rejects_requests_with_discussion_type_not_in_the_allowed_enum(client):
    response = await client.post(
        '/api/threads',
        json={
            'to': 'agent-b',
            'subject': 'bad type',
            'body': 'hello',
            'discussion_type': 'invalid_type',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 422


async def test_it_returns_the_created_thread_with_primary_recipient_and_recipients_list(client):
    response = await client.post(
        '/api/threads',
        json={
            'to_participants': ['agent-b', 'agent-c'],
            'subject': 'multi recip response',
            'body': 'check response shape',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 201
    data = response.json()
    assert data['subject'] == 'multi recip response'
    assert data['created_by'] == 'agent-a'
    assert 'recipients' in data
    assert 'agent-b' in data['recipients']
    assert 'agent-c' in data['recipients']

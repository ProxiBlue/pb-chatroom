"""Tests for REST message and ack endpoints (Task 008)."""

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


@pytest.fixture
async def thread_id(client):
    """Create a thread from agent-a to agent-b, return its id."""
    r = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'hello', 'body': 'seed'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 201
    return r.json()['id']


async def test_it_appends_a_message_to_an_existing_thread_and_returns_201(client, thread_id):
    response = await client.post(
        f'/api/threads/{thread_id}/messages',
        json={'body': 'hello back'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert response.status_code == 201
    data = response.json()
    assert data['body'] == 'hello back'
    assert data['from_participant'] == 'agent-b'
    assert data['kind'] == 'message'
    assert data['thread_id'] == thread_id


async def test_it_returns_404_when_posting_a_message_to_an_unknown_thread(client):
    response = await client.post(
        '/api/threads/00000000-0000-0000-0000-000000000000/messages',
        json={'body': 'hello'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 404


async def test_it_returns_403_when_the_caller_is_not_a_participant_of_the_thread(
    client, thread_id
):
    response = await client.post(
        f'/api/threads/{thread_id}/messages',
        json={'body': 'intruder'},
        headers={'X-PB-Chatroom-Participant': 'agent-c'},
    )
    assert response.status_code == 403


async def test_it_infers_the_recipient_as_the_other_participant_of_the_thread(
    client, thread_id
):
    # agent-b replies → recipient should be agent-a (the creator)
    response = await client.post(
        f'/api/threads/{thread_id}/messages',
        json={'body': 'reply from b'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert response.status_code == 201
    data = response.json()
    assert data['from_participant'] == 'agent-b'
    assert data['to_participant'] == 'agent-a'


async def test_it_acks_a_thread_returning_the_ack_message_and_flipping_status_to_acked(
    client, thread_id
):
    response = await client.post(
        f'/api/threads/{thread_id}/ack',
        json={'body': 'got it'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['kind'] == 'ack'
    assert data['body'] == 'got it'
    assert data['thread_id'] == thread_id

    # verify thread is now acked
    thread_resp = await client.get(f'/api/threads/{thread_id}')
    assert thread_resp.json()['status'] == 'acked'


async def test_it_allows_ack_body_to_be_omitted_defaulting_to_ack(client, thread_id):
    response = await client.post(
        f'/api/threads/{thread_id}/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['body'] == 'Ack'


async def test_it_returns_404_when_acking_an_unknown_thread(client):
    response = await client.post(
        '/api/threads/00000000-0000-0000-0000-000000000000/ack',
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 404

"""Tests for REST thread endpoints (Task 007)."""

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


async def test_it_creates_a_thread_and_returns_201_with_the_thread_payload(client):
    response = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'hello', 'body': 'first message'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert response.status_code == 201
    data = response.json()
    assert data['subject'] == 'hello'
    assert data['created_by'] == 'agent-a'
    assert data['status'] == 'open'
    assert 'id' in data
    assert 'created_at' in data
    assert 'last_message_at' in data


async def test_it_returns_400_when_x_pb_chatroom_participant_header_is_missing_on_post(client):
    response = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'hello', 'body': 'first message'},
    )
    assert response.status_code == 400
    assert response.json() == {'detail': 'X-PB-Chatroom-Participant header required'}


async def test_it_returns_400_when_x_pb_chatroom_participant_header_value_is_malformed(client):
    response = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'hello', 'body': 'first message'},
        headers={'X-PB-Chatroom-Participant': 'Agent B!!'},
    )
    assert response.status_code == 400
    assert response.json() == {'detail': 'invalid participant id'}


async def test_it_lists_all_threads(client):
    await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'thread 1', 'body': 'msg'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    await client.post(
        '/api/threads',
        json={'to': 'agent-c', 'subject': 'thread 2', 'body': 'msg'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    response = await client.get('/api/threads')
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_it_filters_listed_threads_by_to_query_parameter(client):
    await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'for b', 'body': 'msg'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    await client.post(
        '/api/threads',
        json={'to': 'agent-c', 'subject': 'for c', 'body': 'msg'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    response = await client.get('/api/threads?to=agent-b')
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['subject'] == 'for b'


async def test_it_filters_listed_threads_by_status_query_parameter(sqlite_path, test_app):
    from pb_chatroom.store.threads import update_thread_status

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url='http://test') as c:
        r1 = await c.post(
            '/api/threads',
            json={'to': 'agent-b', 'subject': 'open thread', 'body': 'msg'},
            headers={'X-PB-Chatroom-Participant': 'agent-a'},
        )
        r2 = await c.post(
            '/api/threads',
            json={'to': 'agent-b', 'subject': 'acked thread', 'body': 'msg'},
            headers={'X-PB-Chatroom-Participant': 'agent-a'},
        )
        thread_id = r2.json()['id']
        await update_thread_status(sqlite_path, thread_id, 'acked')

        response = await c.get('/api/threads?status=open')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['subject'] == 'open thread'


async def test_it_returns_404_for_get_on_an_unknown_thread_id(client):
    response = await client.get('/api/threads/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


async def test_it_returns_the_seed_message_under_the_thread_when_fetched_by_id(client):
    r = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'hello', 'body': 'seed body'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    thread_id = r.json()['id']
    response = await client.get(f'/api/threads/{thread_id}')
    assert response.status_code == 200
    data = response.json()
    assert data['subject'] == 'hello'
    assert len(data['messages']) == 1
    msg = data['messages'][0]
    assert msg['body'] == 'seed body'
    assert msg['from_participant'] == 'agent-a'
    assert msg['to_participant'] == 'agent-b'

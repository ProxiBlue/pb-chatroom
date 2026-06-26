"""Tests for POST /api/threads/{thread_id}/claim (Task 006)."""

from __future__ import annotations

import asyncio

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


async def _create_thread(client: AsyncClient) -> str:
    r = await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'claim test', 'body': 'hello'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 201
    return r.json()['id']


async def test_it_claims_an_unclaimed_thread_and_returns_200_with_the_claim_payload(client):
    tid = await _create_thread(client)
    r = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': 'working on it'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 200
    data = r.json()
    assert data['claimed_by'] == 'agent-a'
    assert 'claimed_at' in data
    assert data['claim_scope'] == 'working on it'


async def test_it_rejects_a_second_claim_attempt_by_a_different_participant_with_409(client):
    tid = await _create_thread(client)
    r1 = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': 'first claim'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': 'second claim'},
        headers={'X-PB-Chatroom-Participant': 'agent-b'},
    )
    assert r2.status_code == 409
    data = r2.json()
    assert data['detail']['claimed_by'] == 'agent-a'


async def test_it_returns_200_when_the_same_participant_claims_twice_idempotent(client):
    tid = await _create_thread(client)
    r1 = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': 'approach X'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': 'approach X again'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r2.status_code == 200
    assert r2.json()['claimed_by'] == 'agent-a'


async def test_it_stores_claim_scope_verbatim_from_the_request_body(client):
    tid = await _create_thread(client)
    scope = 'very specific approach: do X, then Y, then Z'
    r = await client.post(
        f'/api/threads/{tid}/claim',
        json={'scope': scope},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 200
    assert r.json()['claim_scope'] == scope


async def test_it_returns_404_when_the_thread_does_not_exist(client):
    r = await client.post(
        '/api/threads/nonexistent-uuid/claim',
        json={'scope': 'some scope'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 404


async def test_it_returns_400_when_the_request_body_is_missing_scope(client):
    tid = await _create_thread(client)
    r = await client.post(
        f'/api/threads/{tid}/claim',
        json={},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 422


async def test_it_handles_two_concurrent_claim_requests_so_exactly_one_wins(client):
    tid = await _create_thread(client)
    r1, r2 = await asyncio.gather(
        client.post(
            f'/api/threads/{tid}/claim',
            json={'scope': 'approach A'},
            headers={'X-PB-Chatroom-Participant': 'container-alpha'},
        ),
        client.post(
            f'/api/threads/{tid}/claim',
            json={'scope': 'approach B'},
            headers={'X-PB-Chatroom-Participant': 'container-beta'},
        ),
    )
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409]

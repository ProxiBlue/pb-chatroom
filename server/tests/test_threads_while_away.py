"""Tests for GET /api/threads?discussion_types=...&since=... (Task 019)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace('+00:00', 'Z')


def _since_24h() -> str:
    return _iso(datetime.now(UTC) - timedelta(hours=24))


async def test_it_returns_threads_with_latest_message_discussion_type_escalation_in_the_last_24_hours(  # noqa: E501
    client,
):
    r = await client.post(
        '/api/threads',
        json={
            'to': 'agent-b',
            'subject': 'urgent',
            'body': 'help',
            'discussion_type': 'escalation',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 201

    response = await client.get(
        f'/api/threads?discussion_types=escalation&status=open&since={_since_24h()}'
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['subject'] == 'urgent'


async def test_it_returns_threads_with_latest_message_discussion_type_postmortem_in_the_last_24_hours(  # noqa: E501
    client,
):
    r = await client.post(
        '/api/threads',
        json={
            'to': 'agent-b',
            'subject': 'incident review',
            'body': 'details',
            'discussion_type': 'postmortem',
        },
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )
    assert r.status_code == 201

    response = await client.get(
        f'/api/threads?discussion_types=postmortem&status=open&since={_since_24h()}'
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]['subject'] == 'incident review'


async def test_it_does_not_return_threads_whose_discussion_type_is_free_form_null(
    client,
):
    await client.post(
        '/api/threads',
        json={'to': 'agent-b', 'subject': 'casual chat', 'body': 'hey'},
        headers={'X-PB-Chatroom-Participant': 'agent-a'},
    )

    response = await client.get(
        f'/api/threads?discussion_types=escalation,postmortem&status=open&since={_since_24h()}'
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


async def test_it_does_not_return_threads_older_than_24_hours(sqlite_path, test_app):
    from pb_chatroom.store.schema import connect

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url='http://test') as c:
        r = await c.post(
            '/api/threads',
            json={
                'to': 'agent-b',
                'subject': 'old escalation',
                'body': 'old',
                'discussion_type': 'escalation',
            },
            headers={'X-PB-Chatroom-Participant': 'agent-a'},
        )
        thread_id = r.json()['id']
        old_ts = _iso(datetime.now(UTC) - timedelta(hours=48))
        async with connect(sqlite_path) as db:
            await db.execute(
                'UPDATE threads SET last_message_at = ? WHERE id = ?',
                (old_ts, thread_id),
            )
            await db.commit()

        response = await c.get(
            f'/api/threads?discussion_types=escalation&status=open&since={_since_24h()}'
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


async def test_it_returns_an_empty_list_when_nothing_matches(client):
    response = await client.get(
        f'/api/threads?discussion_types=escalation,postmortem&status=open&since={_since_24h()}'
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_it_accepts_a_configurable_lookback_window_via_since_parameter(sqlite_path, test_app):
    from pb_chatroom.store.schema import connect

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url='http://test') as c:
        r = await c.post(
            '/api/threads',
            json={
                'to': 'agent-b',
                'subject': 'week-old escalation',
                'body': 'details',
                'discussion_type': 'escalation',
            },
            headers={'X-PB-Chatroom-Participant': 'agent-a'},
        )
        thread_id = r.json()['id']
        ts_3d_ago = _iso(datetime.now(UTC) - timedelta(days=3))
        async with connect(sqlite_path) as db:
            await db.execute(
                'UPDATE threads SET last_message_at = ? WHERE id = ?',
                (ts_3d_ago, thread_id),
            )
            await db.commit()

        # 24h window — should NOT return it
        response_24h = await c.get(
            f'/api/threads?discussion_types=escalation&status=open&since={_since_24h()}'
        )
        assert len(response_24h.json()) == 0

        # 1-week window — SHOULD return it
        since_1w = _iso(datetime.now(UTC) - timedelta(days=7))
        response_1w = await c.get(
            f'/api/threads?discussion_types=escalation&status=open&since={since_1w}'
        )
        assert len(response_1w.json()) == 1
        assert response_1w.json()[0]['subject'] == 'week-old escalation'

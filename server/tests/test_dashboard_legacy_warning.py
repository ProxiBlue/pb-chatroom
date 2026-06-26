"""Tests for dashboard host-agent legacy warning row (Task 018)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from pb_chatroom.app import create_app
from pb_chatroom.settings import Settings
from pb_chatroom.store import init_schema
from pb_chatroom.store.schema import connect


@pytest.fixture
async def app_with_db(sqlite_path):
    """App wired to a fresh per-test SQLite; schema initialised."""
    await init_schema(sqlite_path)
    return create_app(Settings(db_path=sqlite_path))


@pytest.fixture
async def client(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url='http://test') as c:
        yield c


async def _insert_message(db_path, *, from_participant, to_participant, created_at):
    """Direct DB insert bypassing store layer to control created_at timestamp."""
    import json
    import uuid

    async with connect(db_path) as db:
        # Need a thread first
        thread_id = str(uuid.uuid4())
        await db.execute(
            'INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (thread_id, 'test', 'alice', 'open', created_at, created_at),
        )
        msg_id = str(uuid.uuid4())
        await db.execute(
            'INSERT INTO messages (id, thread_id, from_participant, to_participant,'
            ' body, kind, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                msg_id,
                thread_id,
                from_participant,
                to_participant,
                'body',
                'message',
                json.dumps({}),
                created_at,
            ),
        )
        await db.commit()


def _recent_ts():
    """ISO timestamp 1 day ago (within 7-day window)."""
    return (datetime.now(UTC) - timedelta(days=1)).isoformat().replace('+00:00', 'Z')


def _old_ts():
    """ISO timestamp 8 days ago (outside 7-day window)."""
    return (datetime.now(UTC) - timedelta(days=8)).isoformat().replace('+00:00', 'Z')


async def test_it_shows_the_warning_row_when_host_agent_appears_as_a_sender_in_the_last_7_days(
    sqlite_path, app_with_db, client
):
    await _insert_message(
        sqlite_path,
        from_participant='host-agent',
        to_participant='alice',
        created_at=_recent_ts(),
    )
    response = await client.get('/')
    assert response.status_code == 200
    assert 'legacy-warning' in response.text


async def test_it_shows_the_warning_row_when_host_agent_appears_as_a_recipient_in_the_last_7_days(
    sqlite_path, app_with_db, client
):
    await _insert_message(
        sqlite_path,
        from_participant='alice',
        to_participant='host-agent',
        created_at=_recent_ts(),
    )
    response = await client.get('/')
    assert response.status_code == 200
    assert 'legacy-warning' in response.text


async def test_it_does_not_show_the_warning_row_when_host_agent_is_absent_from_the_last_7_days(
    sqlite_path, app_with_db, client
):
    await _insert_message(
        sqlite_path,
        from_participant='alice',
        to_participant='bob',
        created_at=_recent_ts(),
    )
    response = await client.get('/')
    assert response.status_code == 200
    assert 'legacy-warning' not in response.text


async def test_it_does_not_show_the_warning_row_when_host_agent_only_appears_in_older_threads(
    sqlite_path, app_with_db, client
):
    await _insert_message(
        sqlite_path,
        from_participant='host-agent',
        to_participant='alice',
        created_at=_old_ts(),
    )
    response = await client.get('/')
    assert response.status_code == 200
    assert 'legacy-warning' not in response.text


async def test_it_names_the_migration_target_host_or_host_auto_in_the_warning_text(
    sqlite_path, app_with_db, client
):
    await _insert_message(
        sqlite_path,
        from_participant='host-agent',
        to_participant='alice',
        created_at=_recent_ts(),
    )
    response = await client.get('/')
    assert response.status_code == 200
    text = response.text
    assert 'host' in text
    assert 'host-auto' in text

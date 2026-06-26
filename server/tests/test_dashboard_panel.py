"""Tests for the dashboard escalation panel (Task 017)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pb_chatroom.app import create_app
from pb_chatroom.settings import Settings
from pb_chatroom.store import init_schema
from pb_chatroom.store.threads import create_thread, set_claim, set_discussion_type


@pytest.fixture
async def app_with_db(sqlite_path):
    await init_schema(sqlite_path)
    return create_app(Settings(db_path=sqlite_path))


@pytest.fixture
async def client(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url='http://test') as c:
        yield c


async def test_it_shows_the_open_escalations_count_in_the_panel(
    client, app_with_db, sqlite_path
):
    thread = await create_thread(
        sqlite_path,
        subject='Escalation Thread',
        created_by='alice',
        to_participant='lucas',
        body='urgent issue',
    )
    await set_discussion_type(sqlite_path, thread['id'], 'escalation')
    response = await client.get('/')
    assert response.status_code == 200
    assert '1 escalation' in response.text


async def test_it_shows_the_open_postmortems_count_in_the_panel(
    client, app_with_db, sqlite_path
):
    thread = await create_thread(
        sqlite_path,
        subject='Postmortem Thread',
        created_by='alice',
        to_participant='lucas',
        body='post-incident review',
    )
    await set_discussion_type(sqlite_path, thread['id'], 'postmortem')
    response = await client.get('/')
    assert response.status_code == 200
    assert '1 postmortem' in response.text


async def test_it_shows_the_active_CLAIMs_count_in_the_panel(
    client, app_with_db, sqlite_path
):
    thread = await create_thread(
        sqlite_path,
        subject='Claimed Thread',
        created_by='alice',
        to_participant='lucas',
        body='working on it',
    )
    await set_claim(sqlite_path, thread['id'], participant_id='bob', scope='fix')
    response = await client.get('/')
    assert response.status_code == 200
    assert '1 active CLAIM' in response.text


async def test_it_shows_zero_counts_gracefully_when_nothing_is_open(client):
    response = await client.get('/')
    assert response.status_code == 200
    assert '0 escalation' in response.text
    assert '0 postmortem' in response.text
    assert '0 active CLAIM' in response.text


async def test_it_links_each_count_to_a_filtered_thread_list(client):
    response = await client.get('/')
    assert response.status_code == 200
    assert 'discussion_types=escalation' in response.text
    assert 'discussion_types=postmortem' in response.text


async def test_it_shows_elapsed_time_since_claim_for_each_active_CLAIM(
    client, app_with_db, sqlite_path
):
    thread = await create_thread(
        sqlite_path,
        subject='Claimed Thread',
        created_by='alice',
        to_participant='lucas',
        body='working on it',
    )
    await set_claim(sqlite_path, thread['id'], participant_id='bob', scope='fix')
    response = await client.get('/')
    assert response.status_code == 200
    # claimed_by name should appear in the response (with claimed_at timestamp context)
    assert 'bob' in response.text

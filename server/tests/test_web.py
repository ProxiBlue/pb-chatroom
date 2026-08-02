"""Tests for pb_chatroom.web — HTML dashboard (Task 009)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pb_chatroom.app import create_app
from pb_chatroom.settings import Settings
from pb_chatroom.store import init_schema
from pb_chatroom.store.threads import create_thread


@pytest.fixture
async def app_with_db(sqlite_path):
    """App wired to a fresh per-test SQLite; schema initialised."""
    await init_schema(sqlite_path)
    return create_app(Settings(db_path=sqlite_path))


@pytest.fixture
async def client(app_with_db):
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url='http://test') as c:
        yield c


async def test_it_renders_the_threads_list_at_GET_slash_with_a_200_response(client):
    response = await client.get('/')
    assert response.status_code == 200


async def test_it_includes_the_subject_of_each_thread_in_the_rendered_list(
    client, app_with_db, sqlite_path
):
    await create_thread(
        sqlite_path,
        subject='Hello World',
        created_by='alice',
        to_participant='bob',
        body='first message',
    )
    response = await client.get('/')
    assert 'Hello World' in response.text


async def test_it_renders_the_per_thread_view_at_GET_threads_id(sqlite_path, app_with_db, client):
    thread = await create_thread(
        sqlite_path,
        subject='Test Thread',
        created_by='alice',
        to_participant='bob',
        body='hello',
    )
    response = await client.get(f'/threads/{thread["id"]}')
    assert response.status_code == 200
    assert 'Test Thread' in response.text


async def test_it_returns_404_from_GET_threads_id_for_an_unknown_thread(client):
    response = await client.get('/threads/00000000-0000-0000-0000-000000000000')
    assert response.status_code == 404


async def test_it_html_escapes_a_script_like_subject_so_the_literal_text_is_rendered_not_executed(
    sqlite_path, app_with_db, client
):
    await create_thread(
        sqlite_path,
        subject='<script>alert(1)</script>',
        created_by='alice',
        to_participant='bob',
        body='xss test',
    )
    response = await client.get('/')
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text


async def test_it_html_escapes_a_script_like_message_body_in_the_per_thread_view(
    sqlite_path, app_with_db, client
):
    thread = await create_thread(
        sqlite_path,
        subject='Safe Subject',
        created_by='alice',
        to_participant='bob',
        body='<script>alert(2)</script>',
    )
    response = await client.get(f'/threads/{thread["id"]}')
    assert '<script>alert(2)</script>' not in response.text
    assert '&lt;script&gt;' in response.text


async def test_an_open_thread_renders_an_ack_button_that_acks_as_the_seed_recipient(
    sqlite_path, app_with_db, client
):
    thread = await create_thread(
        sqlite_path,
        subject='Needs an ack',
        created_by='container-pps',
        to_participant='host',
        body='question for the operator',
    )
    response = await client.get(f'/threads/{thread["id"]}')
    assert 'id="ack-btn"' in response.text
    # Acks on behalf of the addressed recipient (the entity the ack is owed from).
    assert 'data-ack-as="host"' in response.text
    assert f'data-thread="{thread["id"]}"' in response.text


async def test_an_acked_thread_does_not_render_the_ack_button(
    sqlite_path, app_with_db, client
):
    thread = await create_thread(
        sqlite_path,
        subject='Already handled',
        created_by='container-pps',
        to_participant='host',
        body='resolved',
    )
    # Ack it via the API the button drives, as the seed recipient.
    await client.post(
        f'/api/threads/{thread["id"]}/ack',
        headers={'X-PB-Chatroom-Participant': 'host'},
        json={'body': 'done'},
    )
    response = await client.get(f'/threads/{thread["id"]}')
    assert 'id="ack-btn"' not in response.text


async def test_the_ack_button_target_endpoint_flips_the_thread_to_acked(
    sqlite_path, app_with_db, client
):
    thread = await create_thread(
        sqlite_path,
        subject='Ack round-trip',
        created_by='container-pps',
        to_participant='host',
        body='please ack',
    )
    ack = await client.post(
        f'/api/threads/{thread["id"]}/ack',
        headers={'X-PB-Chatroom-Participant': 'host'},
        json={'body': 'Acked from dashboard'},
    )
    assert ack.status_code == 200
    detail = await client.get(f'/threads/{thread["id"]}')
    assert 'acked' in detail.text

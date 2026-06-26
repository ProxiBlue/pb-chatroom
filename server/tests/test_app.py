"""Tests for pb_chatroom.app — FastAPI skeleton (Task 006)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def run_lifespan(app):
    """Trigger ASGI lifespan startup/shutdown around a block."""
    startup_done: asyncio.Event = asyncio.Event()
    shutdown_queue: asyncio.Queue = asyncio.Queue()

    async def receive():
        if not startup_done.is_set():
            return {'type': 'lifespan.startup'}
        await shutdown_queue.get()
        return {'type': 'lifespan.shutdown'}

    async def send(message):
        if message['type'] == 'lifespan.startup.complete':
            startup_done.set()

    task = asyncio.create_task(app({'type': 'lifespan', 'asgi': {'version': '3.0'}}, receive, send))
    await startup_done.wait()
    try:
        yield
    finally:
        shutdown_queue.put_nowait(None)
        await task


async def test_it_boots_with_default_settings_and_exposes_healthz_returning_200(sqlite_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.settings import Settings

    app = create_app(Settings(db_path=sqlite_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/healthz')

    assert response.status_code == 200


async def test_it_includes_the_resolved_participant_id_in_the_healthz_response(sqlite_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.identity import resolve_participant_id
    from pb_chatroom.settings import Settings

    app = create_app(Settings(db_path=sqlite_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/healthz')

    data = response.json()
    assert data['participant'] == resolve_participant_id()


async def test_it_runs_init_schema_during_lifespan_startup_so_the_db_file_exists(sqlite_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.settings import Settings

    app = create_app(Settings(db_path=sqlite_path))

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url='http://test')
    async with run_lifespan(app), client:
        await client.get('/healthz')

    assert sqlite_path.exists()


async def test_it_accepts_an_injected_settings_override_with_a_custom_db_path(sqlite_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.settings import Settings

    custom_settings = Settings(db_path=sqlite_path)
    app = create_app(custom_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/healthz')

    assert response.status_code == 200


async def test_it_creates_the_parent_directory_of_db_path_if_missing(tmp_path):
    from pb_chatroom.app import create_app
    from pb_chatroom.settings import Settings

    nested_db = tmp_path / 'nested' / 'deep' / 'chatroom.db'
    assert not nested_db.parent.exists()

    app = create_app(Settings(db_path=nested_db))

    async with run_lifespan(app):
        pass

    assert nested_db.parent.exists()
    assert nested_db.exists()

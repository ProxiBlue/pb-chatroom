"""FastAPI application factory for pb-chatroom server."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import threads_router
from .identity import resolve_participant_id
from .settings import Settings
from .store import init_schema
from .web import router as web_router


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        await init_schema(settings.db_path)
        app.state.db_path = settings.db_path
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.db_path = settings.db_path
    app.state.settings = settings
    app.include_router(threads_router)
    app.include_router(web_router)

    @app.get('/healthz')
    async def healthz():
        return {'status': 'ok', 'participant': resolve_participant_id()}

    return app


app = create_app()

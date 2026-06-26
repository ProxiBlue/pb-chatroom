"""Health check FastAPI app factory."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Response


def build_health_app(get_status: Callable[[], dict]) -> FastAPI:
    app = FastAPI()

    @app.get('/healthz', response_model=None)
    def healthz() -> Response | dict:
        status = get_status()
        if status['last_poll_at'] is None:
            return Response(
                content='{"status":"starting"}',
                status_code=503,
                media_type='application/json',
            )
        return status

    return app

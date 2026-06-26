"""Environment-driven settings for pb-chatroom server."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: Path = Path('./data/chatroom.db')
    host: str = '127.0.0.1'
    port: int = 7476
    # Dashboard auto-refresh interval in seconds. 0 disables auto-refresh.
    # Override via env: PB_CHATROOM_REFRESH_INTERVAL_SECONDS=30
    refresh_interval_seconds: int = 10

    model_config = {
        'env_prefix': 'PB_CHATROOM_',
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
    }

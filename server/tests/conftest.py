"""Shared pytest fixtures for the pb-chatroom server suite.

HCF's tdd-worker will land per-feature fixtures here as Phase 1 tasks
implement the FastAPI app, SQLite store, identity resolution, etc.

The intentional minimum scaffold below documents the convention:
each test gets a fresh SQLite via tmp_path; no shared global DB.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def sqlite_path(tmp_path):
    """Per-test SQLite file location. Keeps parallel pytest runs
    isolated — workers spawned by HCF orchestration must not share
    state between tests.
    """
    return tmp_path / 'chatroom.db'

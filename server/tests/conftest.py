"""Shared pytest fixtures for the pb-chatroom server suite.

HCF's tdd-worker will land per-feature fixtures here as Phase 1 tasks
implement the FastAPI app, SQLite store, identity resolution, etc.

The intentional minimum scaffold below documents the convention:
each test gets a fresh SQLite via tmp_path; no shared global DB.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--run-compose-smoke',
        action='store_true',
        default=False,
        help='Run docker-compose 2-service smoke tests (requires Docker)',
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-compose-smoke'):
        skip = pytest.mark.skip(reason='Pass --run-compose-smoke to run')
        for item in items:
            if 'compose_smoke' in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def sqlite_path(tmp_path):
    """Per-test SQLite file location. Keeps parallel pytest runs
    isolated — workers spawned by HCF orchestration must not share
    state between tests.
    """
    return tmp_path / 'chatroom.db'

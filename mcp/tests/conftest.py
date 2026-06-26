"""Shared fixtures for MCP tests."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    """httpx mock transport for simulating server responses without a live process."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'ok': True})

    return httpx.MockTransport(handler)

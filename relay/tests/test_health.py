"""Tests for health.py — GET /healthz endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pb_chatroom_relay.health import build_health_app

CANNED_STATUS = {
    'role_counts': {'responders': 1, 'broadcasters': 1, 'archivers': 1},
    'last_poll_at': '2026-06-26T12:00:00Z',
    'budget_state': {'responder-auto': {'hour_count': 2, 'day_count': 5}},
}


def test_it_returns_200_with_role_counts_last_poll_at_and_budget_state_on_GET_healthz():
    app = build_health_app(get_status=lambda: CANNED_STATUS)
    client = TestClient(app, raise_server_exceptions=True)
    response = client.get('/healthz')
    assert response.status_code == 200
    body = response.json()
    assert 'role_counts' in body
    assert 'last_poll_at' in body
    assert 'budget_state' in body


def test_it_reflects_the_current_budget_snapshot_from_the_budget_engine_in_the_response():
    budget = {'responder-auto': {'hour_count': 7, 'day_count': 12}}
    status = {**CANNED_STATUS, 'budget_state': budget}
    app = build_health_app(get_status=lambda: status)
    client = TestClient(app)
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json()['budget_state'] == budget


def test_it_reflects_the_polling_loop_last_poll_at_timestamp_in_the_response():
    ts = '2026-06-26T15:30:00Z'
    status = {**CANNED_STATUS, 'last_poll_at': ts}
    app = build_health_app(get_status=lambda: status)
    client = TestClient(app)
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.json()['last_poll_at'] == ts


def test_it_returns_503_when_the_polling_loop_has_not_yet_completed_its_first_tick():
    status = {**CANNED_STATUS, 'last_poll_at': None}
    app = build_health_app(get_status=lambda: status)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/healthz')
    assert response.status_code == 503

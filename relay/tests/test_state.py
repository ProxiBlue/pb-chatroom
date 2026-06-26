"""Tests for the relay state persistence layer."""

from __future__ import annotations

import json

import pytest

from pb_chatroom_relay.state import State


def test_it_returns_a_fresh_state_object_when_the_state_file_does_not_exist(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    assert state.poll_cursor is None
    assert state.archive_cursor is None
    assert state.budget == {}
    assert state.broadcaster_state == {}


def test_it_loads_the_state_file_when_it_exists_with_valid_JSON(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    data = {
        'poll_cursor': '2026-06-26T00:00:00Z',
        'archive_cursor': '2026-06-26T01:00:00Z',
        'budget': {
            'host-auto': {
                'hour_bucket': '2026062612',
                'hour_count': 3,
                'day_bucket': '20260626',
                'day_count': 17,
            }
        },
        'broadcaster_state': {},
    }
    path.write_text(json.dumps(data))
    state = State.load(path)
    assert state.poll_cursor == '2026-06-26T00:00:00Z'
    assert state.archive_cursor == '2026-06-26T01:00:00Z'
    assert state.budget == data['budget']


def test_it_raises_a_clear_error_when_the_state_file_exists_but_is_malformed_JSON(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    path.write_text('not valid json {{{{')
    with pytest.raises(ValueError, match='malformed'):
        State.load(path)


def test_it_writes_state_atomically_using_a_tmp_file_plus_rename(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    state.poll_cursor = '2026-06-26T10:00:00Z'
    state.save(path)
    # tmp file must be gone after save
    assert not path.with_suffix('.tmp').exists()
    # actual file must exist
    assert path.exists()


def test_it_round_trips_poll_cursor_and_archive_cursor_through_save_and_reload(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    state.poll_cursor = '2026-06-26T08:00:00Z'
    state.archive_cursor = '2026-06-26T09:00:00Z'
    state.save(path)

    reloaded = State.load(path)
    assert reloaded.poll_cursor == '2026-06-26T08:00:00Z'
    assert reloaded.archive_cursor == '2026-06-26T09:00:00Z'


def test_it_round_trips_per_responder_budget_counters_through_save_and_reload(tmp_state_dir):
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    state.budget = {
        'host-auto': {
            'hour_bucket': '2026062612',
            'hour_count': 5,
            'day_bucket': '20260626',
            'day_count': 42,
        }
    }
    state.save(path)

    reloaded = State.load(path)
    assert reloaded.budget['host-auto']['hour_count'] == 5
    assert reloaded.budget['host-auto']['day_count'] == 42

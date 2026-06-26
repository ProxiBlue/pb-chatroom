"""Tests for the BudgetEngine — per-responder hourly + daily budget counters."""

from __future__ import annotations

from datetime import datetime, timezone

from pb_chatroom_relay.budget import BudgetEngine, Clock, FakeClock
from pb_chatroom_relay.config import BudgetConfig
from pb_chatroom_relay.state import State

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)  # 2026-06-26 12:00 UTC


def _engine(
    clock: Clock,
    tmp_state_dir,
    *,
    hourly: int = 5,
    daily: int = 20,
    responder: str = 'host-auto',
) -> tuple[BudgetEngine, object]:
    """Build a BudgetEngine with a single responder registered."""
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    engine = BudgetEngine(state=state, clock=clock, state_path=path)
    engine.add_responder(
        responder,
        BudgetConfig(max_invocations_per_hour=hourly, max_invocations_per_day=daily),
    )
    return engine, path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_it_allows_dispatch_when_counters_are_below_both_hourly_and_daily_caps(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir)
    assert engine.can_dispatch('host-auto') is True


def test_it_refuses_dispatch_when_the_hourly_cap_is_reached(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir, hourly=3, daily=100)
    for _ in range(3):
        engine.record_dispatch('host-auto')
    assert engine.can_dispatch('host-auto') is False


def test_it_refuses_dispatch_when_the_daily_cap_is_reached(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir, hourly=100, daily=3)
    for _ in range(3):
        engine.record_dispatch('host-auto')
    assert engine.can_dispatch('host-auto') is False


def test_it_resets_the_hourly_counter_when_the_hour_boundary_crosses(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir, hourly=3, daily=100)
    for _ in range(3):
        engine.record_dispatch('host-auto')
    assert engine.can_dispatch('host-auto') is False

    # Advance past the hour boundary
    clock.advance(hours=1)
    assert engine.can_dispatch('host-auto') is True


def test_it_resets_the_daily_counter_when_the_day_boundary_crosses(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir, hourly=100, daily=3)
    for _ in range(3):
        engine.record_dispatch('host-auto')
    assert engine.can_dispatch('host-auto') is False

    # Advance past the day boundary
    clock.advance(days=1)
    assert engine.can_dispatch('host-auto') is True


def test_it_persists_counters_through_save_and_reload_via_the_state_layer(tmp_state_dir):
    clock = FakeClock(_T0)
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    engine = BudgetEngine(state=state, clock=clock, state_path=path)
    engine.add_responder(
        'host-auto',
        BudgetConfig(max_invocations_per_hour=10, max_invocations_per_day=50),
    )

    engine.record_dispatch('host-auto')
    engine.record_dispatch('host-auto')

    # Reload from disk
    state2 = State.load(path)
    engine2 = BudgetEngine(state=state2, clock=clock, state_path=path)
    engine2.add_responder(
        'host-auto',
        BudgetConfig(max_invocations_per_hour=10, max_invocations_per_day=50),
    )

    snap = engine2.snapshot()
    assert snap['host-auto']['hour_count'] == 2
    assert snap['host-auto']['day_count'] == 2


def test_it_returns_a_snapshot_dict_suitable_for_the_healthcheck_endpoint(tmp_state_dir):
    clock = FakeClock(_T0)
    engine, _ = _engine(clock, tmp_state_dir, hourly=5, daily=20)
    engine.record_dispatch('host-auto')

    snap = engine.snapshot()
    assert 'host-auto' in snap
    entry = snap['host-auto']
    assert 'hour_bucket' in entry
    assert 'hour_count' in entry
    assert 'day_bucket' in entry
    assert 'day_count' in entry
    assert entry['hour_count'] == 1
    assert entry['day_count'] == 1

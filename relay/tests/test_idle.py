"""Tests for IdleSupervisor — idle-threshold + gate checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pb_chatroom_relay.config import ActiveWindowConfig, BroadcasterConfig
from pb_chatroom_relay.idle import IdleSupervisor
from pb_chatroom_relay.state import State

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build _T0 as a local-aware datetime at 10:00 local time.
# This ensures now.astimezone().hour == 10 regardless of the system timezone.
_LOCAL_TZ = datetime.now(timezone.utc).astimezone().tzinfo
_T0 = datetime(2026, 6, 26, 10, 0, 0, tzinfo=_LOCAL_TZ)

_WINDOW = ActiveWindowConfig(start_hour_local=8, end_hour_local=18)


def _cfg(
    idle_minutes: int = 30,
    min_hours_between: int = 2,
    max_per_day: int = 5,
    window: ActiveWindowConfig | None = None,
) -> BroadcasterConfig:
    return BroadcasterConfig(
        enabled=True,
        idle_threshold_minutes=idle_minutes,
        min_hours_between=min_hours_between,
        max_per_day=max_per_day,
        active_window=window or _WINDOW,
    )


def _supervisor(
    tmp_state_dir,
    last_activity: datetime | None,
) -> tuple[IdleSupervisor, object]:
    path = tmp_state_dir / 'state.json'
    state = State.load(path)
    sup = IdleSupervisor(
        state=state,
        state_path=path,
        last_activity_getter=lambda: last_activity,
    )
    return sup, path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_it_emits_when_idle_threshold_has_elapsed_and_all_gates_pass(tmp_state_dir):
    # last activity 60 min ago, window open, no prior emissions
    last_activity = _T0 - timedelta(minutes=60)
    sup, _ = _supervisor(tmp_state_dir, last_activity)
    cfg = _cfg(idle_minutes=30, min_hours_between=2, max_per_day=5)
    assert sup.should_emit('check_in', cfg, _T0) is True


def test_it_refuses_to_emit_when_current_local_hour_is_before_active_window_start_hour_local(
    tmp_state_dir,
):
    # T0 = 10:00 UTC, but we put window start at 11 — should refuse
    last_activity = _T0 - timedelta(minutes=60)
    sup, _ = _supervisor(tmp_state_dir, last_activity)
    window = ActiveWindowConfig(start_hour_local=11, end_hour_local=18)
    cfg = _cfg(idle_minutes=30, window=window)
    assert sup.should_emit('check_in', cfg, _T0) is False


def test_it_refuses_to_emit_when_current_local_hour_is_after_active_window_end_hour_local(
    tmp_state_dir,
):
    # T0 = 10:00 UTC, put window end at 9 — should refuse
    last_activity = _T0 - timedelta(minutes=60)
    sup, _ = _supervisor(tmp_state_dir, last_activity)
    window = ActiveWindowConfig(start_hour_local=8, end_hour_local=9)
    cfg = _cfg(idle_minutes=30, window=window)
    assert sup.should_emit('check_in', cfg, _T0) is False


def test_it_refuses_to_emit_when_min_hours_between_has_not_elapsed_since_last_emission(
    tmp_state_dir,
):
    last_activity = _T0 - timedelta(minutes=60)
    sup, path = _supervisor(tmp_state_dir, last_activity)
    cfg = _cfg(idle_minutes=30, min_hours_between=4, max_per_day=5)
    # Record an emission 1 hour ago — less than min_hours_between=4
    sup.record_emission('check_in', _T0 - timedelta(hours=1))
    assert sup.should_emit('check_in', cfg, _T0) is False


def test_it_refuses_to_emit_when_todays_emission_count_has_reached_max_per_day(tmp_state_dir):
    last_activity = _T0 - timedelta(minutes=60)
    sup, _ = _supervisor(tmp_state_dir, last_activity)
    cfg = _cfg(idle_minutes=30, min_hours_between=0, max_per_day=2)
    # Record 2 emissions today (with min_hours_between=0 so they go through)
    sup.record_emission('check_in', _T0 - timedelta(hours=2))
    sup.record_emission('check_in', _T0 - timedelta(hours=1))
    assert sup.should_emit('check_in', cfg, _T0) is False


def test_it_refuses_to_emit_when_idle_threshold_has_not_elapsed(tmp_state_dir):
    # last activity only 10 min ago, threshold is 30 min
    last_activity = _T0 - timedelta(minutes=10)
    sup, _ = _supervisor(tmp_state_dir, last_activity)
    cfg = _cfg(idle_minutes=30, min_hours_between=0, max_per_day=5)
    assert sup.should_emit('check_in', cfg, _T0) is False


def test_it_persists_the_last_emission_timestamp_and_the_daily_count_via_the_state_layer(
    tmp_state_dir,
):
    last_activity = _T0 - timedelta(minutes=60)
    sup, path = _supervisor(tmp_state_dir, last_activity)
    sup.record_emission('check_in', _T0)

    # Reload from disk
    state2 = State.load(path)
    sup2 = IdleSupervisor(
        state=state2,
        state_path=path,
        last_activity_getter=lambda: last_activity,
    )
    entry = state2.broadcaster_state.get('check_in', {})
    assert entry['last_emitted_at'] == _T0.isoformat()
    assert entry['day_count'] == 1
    assert entry['day_bucket'] is not None

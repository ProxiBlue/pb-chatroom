"""Budget enforcement engine — per-responder hourly + daily dispatch limits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from pb_chatroom_relay.config import BudgetConfig
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Clock protocol + implementations
# ---------------------------------------------------------------------------


class Clock(Protocol):
    def now(self) -> datetime: ...


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: Any) -> None:
        """Advance time by `timedelta(**kwargs)` (e.g. hours=1, days=1)."""
        self._now += timedelta(**kwargs)


# ---------------------------------------------------------------------------
# Bucket helpers
# ---------------------------------------------------------------------------


def _hour_bucket(dt: datetime) -> str:
    """Return YYYYMMDDHH string for the hour containing *dt* (UTC)."""
    utc = dt.astimezone(UTC)
    return utc.strftime('%Y%m%d%H')


def _day_bucket(dt: datetime) -> str:
    """Return YYYYMMDD string for the day containing *dt* (UTC)."""
    utc = dt.astimezone(UTC)
    return utc.strftime('%Y%m%d')


# ---------------------------------------------------------------------------
# BudgetEngine
# ---------------------------------------------------------------------------


class BudgetEngine:
    """Tracks per-responder hourly/daily dispatch counts against configured caps.

    The engine mutates `state.budget` in-place and persists after every
    `record_dispatch` call.
    """

    def __init__(self, state: State, clock: Clock, state_path: Path) -> None:
        self._state = state
        self._clock = clock
        self._state_path = state_path
        self._limits: dict[str, BudgetConfig] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_responder(self, name: str, budget_config: BudgetConfig) -> None:
        """Register budget limits for *name*."""
        self._limits[name] = budget_config

    def can_dispatch(self, name: str) -> bool:
        """Return True iff *name* is within both hourly and daily caps."""
        cfg = self._limits.get(name)
        if cfg is None:
            return True  # unknown responder — no limits registered

        now = self._clock.now()
        entry = self._state.budget.get(name, {})

        hour_count = self._current_hour_count(entry, now)
        day_count = self._current_day_count(entry, now)

        if cfg.max_invocations_per_hour > 0 and hour_count >= cfg.max_invocations_per_hour:
            return False
        if cfg.max_invocations_per_day > 0 and day_count >= cfg.max_invocations_per_day:
            return False
        return True

    def record_dispatch(self, name: str) -> None:
        """Increment counters for *name* and persist state to disk."""
        now = self._clock.now()
        entry = self._state.budget.get(name, {})

        hb = _hour_bucket(now)
        db = _day_bucket(now)

        hour_count = self._current_hour_count(entry, now) + 1
        day_count = self._current_day_count(entry, now) + 1

        self._state.budget[name] = {
            'hour_bucket': hb,
            'hour_count': hour_count,
            'day_bucket': db,
            'day_count': day_count,
        }
        self._state.save(self._state_path)

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of the current budget state (suitable for healthcheck)."""
        now = self._clock.now()
        result: dict[str, Any] = {}
        for name in self._limits:
            entry = self._state.budget.get(name, {})
            result[name] = {
                'hour_bucket': _hour_bucket(now),
                'hour_count': self._current_hour_count(entry, now),
                'day_bucket': _day_bucket(now),
                'day_count': self._current_day_count(entry, now),
            }
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _current_hour_count(self, entry: dict[str, Any], now: datetime) -> int:
        """Return the hour count if bucket matches *now*, else 0."""
        if entry.get('hour_bucket') == _hour_bucket(now):
            return int(entry.get('hour_count', 0))
        return 0

    def _current_day_count(self, entry: dict[str, Any], now: datetime) -> int:
        """Return the day count if bucket matches *now*, else 0."""
        if entry.get('day_bucket') == _day_bucket(now):
            return int(entry.get('day_count', 0))
        return 0

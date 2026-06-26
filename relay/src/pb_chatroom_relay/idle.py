"""Idle supervisor — decides when a broadcaster should fire based on chatroom inactivity."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pb_chatroom_relay.config import BroadcasterConfig
from pb_chatroom_relay.state import State


def _local_day_bucket(dt: datetime) -> str:
    """Return YYYYMMDD string based on *dt*'s local date."""
    local = dt.astimezone()
    return local.strftime('%Y%m%d')


class IdleSupervisor:
    """Decide whether a broadcaster should emit an idle notification.

    Args:
        state: Mutable State object (broadcaster_state dict is mutated in-place).
        state_path: Path where state is persisted after each record_emission call.
        last_activity_getter: Callable returning the most recent chatroom activity
            timestamp, or None if no activity has been recorded.
    """

    def __init__(
        self,
        state: State,
        state_path: Path,
        last_activity_getter: Callable[[], datetime | None],
    ) -> None:
        self._state = state
        self._state_path = state_path
        self._last_activity_getter = last_activity_getter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_emit(
        self,
        broadcaster_name: str,
        broadcaster_config: BroadcasterConfig,
        now: datetime,
    ) -> bool:
        """Return True only when ALL gate conditions pass."""
        # 1. Active window check
        if broadcaster_config.active_window is not None:
            local_hour = now.astimezone().hour
            win = broadcaster_config.active_window
            if not (win.start_hour_local <= local_hour < win.end_hour_local):
                return False

        # 2. Idle threshold check
        last_activity = self._last_activity_getter()
        if last_activity is not None:
            elapsed_minutes = (now - last_activity).total_seconds() / 60
            if elapsed_minutes < broadcaster_config.idle_threshold_minutes:
                return False
        # if last_activity is None — treat as idle since dawn of time, allow

        # 3. min_hours_between check
        entry = self._state.broadcaster_state.get(broadcaster_name, {})
        last_emitted_str: str | None = entry.get('last_emitted_at')
        if last_emitted_str is not None and broadcaster_config.min_hours_between > 0:
            last_emitted = datetime.fromisoformat(last_emitted_str)
            elapsed_hours = (now - last_emitted).total_seconds() / 3600
            if elapsed_hours < broadcaster_config.min_hours_between:
                return False

        # 4. max_per_day check
        today_bucket = _local_day_bucket(now)
        if entry.get('day_bucket') == today_bucket:
            day_count = int(entry.get('day_count', 0))
            if day_count >= broadcaster_config.max_per_day:
                return False

        return True

    def record_emission(self, broadcaster_name: str, now: datetime) -> None:
        """Persist last-emission timestamp and increment today's count."""
        entry = dict(self._state.broadcaster_state.get(broadcaster_name, {}))
        today_bucket = _local_day_bucket(now)

        if entry.get('day_bucket') == today_bucket:
            day_count = int(entry.get('day_count', 0)) + 1
        else:
            day_count = 1

        entry['last_emitted_at'] = now.isoformat()
        entry['day_bucket'] = today_bucket
        entry['day_count'] = day_count

        self._state.broadcaster_state[broadcaster_name] = entry
        self._state.save(self._state_path)

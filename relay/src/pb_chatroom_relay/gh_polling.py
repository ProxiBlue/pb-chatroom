"""GhPoller — polls GitHub issue list per configured repos, yields newly eligible tickets."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pb_chatroom_relay.config import GhPollingConfig
from pb_chatroom_relay.dispatcher import FakeSubprocessRunner, SubprocessRunner
from pb_chatroom_relay.state import State


class GhPoller:
    """Poll configured GitHub repos for newly eligible issues."""

    def __init__(
        self,
        config: GhPollingConfig,
        state: State,
        state_path: Path | None,
        runner: SubprocessRunner | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._state_path = state_path
        self._runner: SubprocessRunner = runner or FakeSubprocessRunner()
        # Overrideable clock for testing
        self._now: Callable[[], datetime] = lambda: datetime.now(tz=UTC)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def poll_once(self) -> list[dict]:
        """Poll all configured repos once; return list of newly eligible ticket dicts."""
        results: list[dict] = []
        for repo in self._config.repos:
            tickets = await self._poll_repo(repo)
            results.extend(tickets)
        if results and self._state_path is not None:
            self._state.save(self._state_path)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _poll_repo(self, repo: str) -> list[dict]:
        argv = [
            'gh',
            'issue',
            'list',
            '--repo',
            repo,
            '--json',
            'number,title,labels,createdAt,url',
            '--limit',
            '50',
        ]
        try:
            stdout, _stderr, returncode = await self._runner.run(
                argv=argv,
                cwd=None,
                stdin_data=b'',
                timeout_seconds=30.0,
            )
        except Exception:
            return []

        if returncode != 0:
            return []

        try:
            raw_issues: list[dict] = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return []

        cursor_str = self._state.gh_cursor.get(repo)
        cursor = int(cursor_str) if cursor_str else 0

        eligible: list[dict] = []
        now = self._now()

        for issue in raw_issues:
            number = issue.get('number', 0)

            # Skip already-seen issues
            if number <= cursor:
                continue

            # Label filter
            if self._config.eligible_label_filter:
                issue_labels = {
                    lbl['name'] if isinstance(lbl, dict) else lbl
                    for lbl in issue.get('labels', [])
                }
                if not issue_labels.intersection(self._config.eligible_label_filter):
                    continue

            # Age filter
            if self._config.min_age_minutes > 0:
                created_at_str = issue.get('createdAt', '')
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace('Z', '+00:00')
                    )
                    age_minutes = (now - created_at).total_seconds() / 60
                    if age_minutes < self._config.min_age_minutes:
                        continue
                except (ValueError, TypeError):
                    continue

            eligible.append(
                {
                    'number': number,
                    'title': issue.get('title', ''),
                    'labels': [
                        lbl['name'] if isinstance(lbl, dict) else lbl
                        for lbl in issue.get('labels', [])
                    ],
                    'createdAt': issue.get('createdAt', ''),
                    'url': issue.get('url', ''),
                    'repo': repo,
                }
            )

        if eligible:
            max_number = max(t['number'] for t in eligible)
            self._state.gh_cursor[repo] = str(max_number)

        return eligible

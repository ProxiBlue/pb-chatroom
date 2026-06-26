"""Tests for CLI entry point — pb-chatroom-relay console script."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers — minimal responders.json fixture
# ---------------------------------------------------------------------------


def _write_responders(path: Path) -> None:
    data = {
        'responders': {
            'host-auto': {
                'trigger': {'from_pattern': 'container-*', 'subject_keywords': ['fyi']},
                'claude_invocation': {
                    'cwd': '/tmp',
                    'model': 'claude-haiku-4-5',
                    'extra_args': ['--allowed-tools', 'Read'],
                    'system_prompt_addendum': '',
                },
                'budget': {'max_invocations_per_hour': 20, 'max_invocations_per_day': 100},
                'archive_on_ack': False,
            }
        },
        'broadcasters': {},
        'archivers': {},
    }
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Test: run subcommand
# ---------------------------------------------------------------------------


def test_it_runs_the_daemon_when_invoked_with_the_run_subcommand(tmp_path):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)

    daemon_stub = MagicMock()

    def _factory(config):
        return daemon_stub

    with patch('pb_chatroom_relay.cli.asyncio.run') as mock_run:
        mock_run.return_value = None
        result = main(
            [
                '--config', str(config_path),
                '--state-dir', str(tmp_path / 'state'),
                'run',
            ],
            _daemon_factory=_factory,
        )

    assert result == 0
    assert mock_run.called


# ---------------------------------------------------------------------------
# Test: budget subcommand
# ---------------------------------------------------------------------------


def test_it_prints_the_budget_snapshot_as_json_when_invoked_with_the_budget_subcommand(
    tmp_path, capsys
):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)
    state_dir = tmp_path / 'state'
    state_dir.mkdir()

    result = main(
        [
            '--config', str(config_path),
            '--state-dir', str(state_dir),
            'budget',
        ]
    )

    assert result == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert 'host-auto' in parsed


# ---------------------------------------------------------------------------
# Test: dry-run subcommand
# ---------------------------------------------------------------------------


def test_it_prints_the_resolved_claude_argv_and_stdin_body_for_dry_run(tmp_path, capsys):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)

    result = main(
        [
            '--config', str(config_path),
            'dry-run',
            '--responder', 'host-auto',
            '--thread-id', 'abc123',
        ]
    )

    assert result == 0
    captured = capsys.readouterr()
    assert 'argv' in captured.out
    assert 'abc123' in captured.out
    assert 'stdin' in captured.out


# ---------------------------------------------------------------------------
# Test: exit code 2 — no subcommand
# ---------------------------------------------------------------------------


def test_it_returns_exit_code_2_when_no_subcommand_is_given(tmp_path):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)

    result = main(['--config', str(config_path)])

    assert result == 2


# ---------------------------------------------------------------------------
# Test: exit code 2 — dry-run missing args
# ---------------------------------------------------------------------------


def test_it_returns_exit_code_2_when_dry_run_is_missing_responder_or_thread_id(tmp_path):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)

    # missing --thread-id
    result = main(
        ['--config', str(config_path), 'dry-run', '--responder', 'host-auto']
    )
    assert result == 2

    # missing --responder
    result = main(
        ['--config', str(config_path), 'dry-run', '--thread-id', 'abc123']
    )
    assert result == 2


# ---------------------------------------------------------------------------
# Test: config from --config or env var
# ---------------------------------------------------------------------------


def test_it_loads_responders_json_from_path_given_via_config_or_env_var(tmp_path, monkeypatch):
    from pb_chatroom_relay.cli import main

    config_path = tmp_path / 'responders.json'
    _write_responders(config_path)
    state_dir = tmp_path / 'state'
    state_dir.mkdir()

    # via env var
    monkeypatch.setenv('PB_CHATROOM_RELAY_CONFIG', str(config_path))

    result = main(
        [
            '--state-dir', str(state_dir),
            'budget',
        ]
    )

    assert result == 0



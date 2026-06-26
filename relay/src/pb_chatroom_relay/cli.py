"""CLI entry point for pb-chatroom-relay console script."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from pb_chatroom_relay.budget import BudgetEngine, UtcClock
from pb_chatroom_relay.config import load_responders_config
from pb_chatroom_relay.daemon import Daemon
from pb_chatroom_relay.state import State


# ---------------------------------------------------------------------------
# Default daemon factory
# ---------------------------------------------------------------------------


def _default_daemon_factory(config):
    return Daemon(config)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv=None, *, _daemon_factory: Callable | None = None) -> int:
    parser = argparse.ArgumentParser(prog='pb-chatroom-relay')
    parser.add_argument('--config', default=None, help='Path to responders.json')
    parser.add_argument(
        '--state-dir',
        default=None,
        help='Directory for state.json (default: relay/state/)',
    )
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('run')
    sub.add_parser('budget')

    dry_p = sub.add_parser('dry-run')
    dry_p.add_argument('--responder', required=False)
    dry_p.add_argument('--thread-id', required=False)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 2

    # --- config resolution ---
    config_path_str = args.config or os.environ.get(
        'PB_CHATROOM_RELAY_CONFIG', 'relay/responders.json'
    )
    config_path = Path(config_path_str)

    # --- state path resolution ---
    state_dir_str = args.state_dir or 'relay/state'
    state_path = Path(state_dir_str) / 'state.json'

    # --- dispatch ---
    if args.command == 'run':
        return _cmd_run(args, config_path, state_path, _daemon_factory)
    if args.command == 'budget':
        return _cmd_budget(args, config_path, state_path)
    if args.command == 'dry-run':
        return _cmd_dry_run(args, dry_p, config_path)

    # unreachable
    return 2


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def _cmd_run(args, config_path: Path, state_path: Path, daemon_factory: Callable | None) -> int:
    config = load_responders_config(config_path)
    factory = daemon_factory or _default_daemon_factory
    daemon = factory(config)
    asyncio.run(daemon.run())
    return 0


def _cmd_budget(args, config_path: Path, state_path: Path) -> int:
    config = load_responders_config(config_path)
    state = State.load(state_path)
    engine = BudgetEngine(state=state, clock=UtcClock(), state_path=state_path)
    for name, resp in config.responders.items():
        engine.add_responder(name, resp.budget)
    print(json.dumps(engine.snapshot(), indent=2))
    return 0


def _cmd_dry_run(args, dry_p: argparse.ArgumentParser, config_path: Path) -> int:
    if not args.responder or not args.thread_id:
        dry_p.print_help()
        return 2

    config = load_responders_config(config_path)
    responder_config = config.responders.get(args.responder)
    if responder_config is None:
        print(f'Unknown responder: {args.responder}', file=sys.stderr)
        return 1

    inv = responder_config.claude_invocation
    argv_list = ['claude', '--print', '--model', inv.model] + inv.extra_args
    stdin_body = f'Subject: (dry-run)\nFrom: (dry-run)\n\n[thread {args.thread_id}]'
    print(f'argv: {argv_list}')
    print(f'cwd: {inv.cwd}')
    print(f'stdin:\n{stdin_body}')
    return 0

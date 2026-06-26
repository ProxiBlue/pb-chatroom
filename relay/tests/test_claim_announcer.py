"""Tests for pb_chatroom_relay.claim_announcer — ClaimAnnouncer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pb_chatroom_relay.claim_announcer import ClaimAnnouncer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(
    number: int = 1,
    title: str = 'Fix the thing',
    labels: list[str] | None = None,
    url: str | None = None,
    repo: str = 'org/repo',
) -> dict:
    return {
        'number': number,
        'title': title,
        'labels': labels or ['help-wanted'],
        'url': url or f'https://github.com/{repo}/issues/{number}',
        'repo': repo,
    }


def _make_client(thread_id: str = 'thread-001') -> MagicMock:
    client = MagicMock()
    client.create_root_thread = AsyncMock(return_value={'id': thread_id})
    return client


def _make_announcer(
    client=None,
    auto_agents: list[str] | None = None,
    state_path: Path | None = None,
    tmp_path: Path | None = None,
) -> ClaimAnnouncer:
    if client is None:
        client = _make_client()
    if auto_agents is None:
        auto_agents = ['host-auto', 'worker-auto']
    if state_path is None:
        assert tmp_path is not None
        state_path = tmp_path / 'state'
        state_path.mkdir(exist_ok=True)
    return ClaimAnnouncer(client=client, auto_agents=auto_agents, state_path=state_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_it_creates_a_claim_request_thread_on_yield_of_a_new_eligible_ticket(tmp_path):
    client = _make_client()
    announcer = _make_announcer(client=client, tmp_path=tmp_path)
    ticket = _make_ticket()

    result = await announcer.announce(ticket)

    assert result is True
    client.create_root_thread.assert_called_once()
    call_kwargs = client.create_root_thread.call_args.kwargs
    assert call_kwargs['discussion_type'] == 'claim_request'


async def test_it_addresses_the_thread_to_every_auto_participant_in_the_config(tmp_path):
    client = _make_client()
    auto_agents = ['host-auto', 'container-pvcpipesupplies-auto', 'another-auto']
    announcer = _make_announcer(client=client, auto_agents=auto_agents, tmp_path=tmp_path)
    ticket = _make_ticket()

    await announcer.announce(ticket)

    call_kwargs = client.create_root_thread.call_args.kwargs
    assert call_kwargs['to_participants'] == auto_agents


async def test_it_stamps_thread_metadata_with_the_ticket_key(tmp_path):
    client = _make_client()
    announcer = _make_announcer(client=client, tmp_path=tmp_path)
    ticket = _make_ticket(number=42, repo='myorg/myrepo')

    await announcer.announce(ticket)

    call_kwargs = client.create_root_thread.call_args.kwargs
    assert call_kwargs['metadata']['ticket_key'] == 'myorg/myrepo#42'


async def test_it_does_not_announce_the_same_ticket_twice_across_consecutive_polls(tmp_path):
    client = _make_client()
    announcer = _make_announcer(client=client, tmp_path=tmp_path)
    ticket = _make_ticket(number=7, repo='org/repo')

    result1 = await announcer.announce(ticket)
    result2 = await announcer.announce(ticket)

    assert result1 is True
    assert result2 is False
    assert client.create_root_thread.call_count == 1


async def test_it_does_not_announce_a_ticket_when_no_auto_agents_are_configured(tmp_path):
    client = _make_client()
    announcer = _make_announcer(client=client, auto_agents=[], tmp_path=tmp_path)
    ticket = _make_ticket()

    result = await announcer.announce(ticket)

    assert result is False
    client.create_root_thread.assert_not_called()


async def test_it_includes_ticket_title_labels_and_link_in_the_body(tmp_path):
    client = _make_client()
    announcer = _make_announcer(client=client, tmp_path=tmp_path)
    ticket = _make_ticket(
        number=5,
        title='Add dark mode',
        labels=['enhancement', 'ui'],
        url='https://github.com/org/repo/issues/5',
        repo='org/repo',
    )

    await announcer.announce(ticket)

    call_kwargs = client.create_root_thread.call_args.kwargs
    body = call_kwargs['body']
    assert 'Add dark mode' in body
    assert 'enhancement' in body
    assert 'ui' in body
    assert 'https://github.com/org/repo/issues/5' in body

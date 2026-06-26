"""Tests for pb_chatroom_relay.claim_orchestrator — ClaimOrchestrator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from pb_chatroom_relay.budget import FakeClock
from pb_chatroom_relay.claim_orchestrator import ClaimOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> MagicMock:
    client = MagicMock()
    client.post_message = AsyncMock(return_value='msg-001')
    return client


def _make_thread(
    thread_id: str = 'thread-001',
    discussion_type: str = 'claim_request',
    claimed_by: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    if created_at is None:
        created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return {
        'id': thread_id,
        'discussion_type': discussion_type,
        'claimed_by': claimed_by,
        'created_at': created_at.isoformat(),
    }


def _make_orchestrator(
    client=None,
    claim_deadline_seconds: int = 60,
    clock: FakeClock | None = None,
) -> ClaimOrchestrator:
    if client is None:
        client = _make_client()
    if clock is None:
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    return ClaimOrchestrator(
        client=client,
        claim_deadline_seconds=claim_deadline_seconds,
        clock=clock,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_it_starts_a_60s_deadline_timer_when_it_sees_a_new_claim_request_thread():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    orch = _make_orchestrator(clock=clock)
    thread = _make_thread(
        thread_id='t-001',
        discussion_type='claim_request',
        claimed_by=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    await orch.observe_threads([thread])

    # Deadline should now be armed for this thread
    assert 't-001' in orch._armed
    expected_deadline = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=60)
    assert orch._armed['t-001'] == expected_deadline


async def test_it_cancels_the_timer_when_a_claim_is_observed_before_deadline():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    client = _make_client()
    orch = _make_orchestrator(client=client, clock=clock)

    # First observe: no claim yet — arms deadline
    thread_unclaimed = _make_thread(
        thread_id='t-002',
        claimed_by=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread_unclaimed])
    assert 't-002' in orch._armed

    # Advance clock 30s (before deadline) and observe with claim
    clock.advance(seconds=30)
    thread_claimed = _make_thread(
        thread_id='t-002',
        claimed_by='agent-007',
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread_claimed])

    # Deadline should be cancelled
    assert 't-002' not in orch._armed
    # No escalation posted
    client.post_message.assert_not_called()


async def test_it_posts_the_no_claimant_escalation_when_the_deadline_elapses_with_no_claim():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    client = _make_client()
    orch = _make_orchestrator(client=client, clock=clock)

    thread = _make_thread(
        thread_id='t-003',
        claimed_by=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread])

    # Advance past deadline
    clock.advance(seconds=61)
    await orch.observe_threads([thread])

    client.post_message.assert_called_once()
    call_args = client.post_message.call_args
    assert call_args.args[0] == 't-003'
    assert 'no claimant' in call_args.args[1].lower()
    assert 'escalating' in call_args.args[1].lower()


async def test_it_sets_discussion_type_to_escalation_on_the_no_claimant_escalation():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    client = _make_client()
    orch = _make_orchestrator(client=client, clock=clock)

    thread = _make_thread(
        thread_id='t-004',
        claimed_by=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread])

    clock.advance(seconds=61)
    await orch.observe_threads([thread])

    call_kwargs = client.post_message.call_args.kwargs
    assert call_kwargs.get('discussion_type') == 'escalation'


async def test_it_does_not_re_arm_the_deadline_after_a_claim_is_observed_and_cancelled():
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    client = _make_client()
    orch = _make_orchestrator(client=client, clock=clock)

    # Arm the deadline
    thread_unclaimed = _make_thread(
        thread_id='t-005',
        claimed_by=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread_unclaimed])
    assert 't-005' in orch._armed

    # Observe claim before deadline — cancels
    clock.advance(seconds=30)
    thread_claimed = _make_thread(
        thread_id='t-005',
        claimed_by='agent-007',
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    await orch.observe_threads([thread_claimed])
    assert 't-005' not in orch._armed

    # Observe claim again — should NOT re-arm
    clock.advance(seconds=100)
    await orch.observe_threads([thread_claimed])
    assert 't-005' not in orch._armed
    client.post_message.assert_not_called()


async def test_it_tolerates_being_restarted_mid_deadline_resumes_from_thread_created_at():
    # Thread created 90s ago — already past 60s deadline
    thread_created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    now = thread_created_at + timedelta(seconds=90)
    clock = FakeClock(now)
    client = _make_client()
    # Fresh orchestrator (simulates restart — no prior armed state)
    orch = _make_orchestrator(client=client, clock=clock)

    thread = _make_thread(
        thread_id='t-006',
        claimed_by=None,
        created_at=thread_created_at,
    )

    # First observe after restart — deadline already past, should escalate immediately
    await orch.observe_threads([thread])

    client.post_message.assert_called_once()
    call_args = client.post_message.call_args
    assert call_args.args[0] == 't-006'
    assert call_args.kwargs.get('discussion_type') == 'escalation'

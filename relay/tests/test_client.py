"""Tests for ChatroomClient — async httpx wrapper around the chatroom REST API."""

from __future__ import annotations

import json

import httpx
import pytest

from pb_chatroom_relay.client import ChatroomClient


def _make_transport(routes: list[tuple[str, str, int, object]]) -> httpx.MockTransport:
    """Build a MockTransport from a list of (method, url_pattern, status, body) tuples."""

    def handler(request: httpx.Request) -> httpx.Response:
        for method, url_substr, status, body in routes:
            if request.method == method and url_substr in str(request.url):
                return httpx.Response(status, json=body)
        return httpx.Response(404, json={'detail': 'not found'})

    return httpx.MockTransport(handler)


PARTICIPANT = 'alice-auto'
BASE_URL = 'http://chatroom.local'


@pytest.fixture
def recorded_requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def client_with_capture(recorded_requests):
    """Client whose transport records every outgoing request."""

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    return ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)


# ---------------------------------------------------------------------------
# Requirement 1: X-PB-Chatroom-Participant header on every request
# ---------------------------------------------------------------------------


async def test_it_sends_X_PB_Chatroom_Participant_header_on_every_request(
    client_with_capture, recorded_requests
):
    await client_with_capture.list_threads()
    assert len(recorded_requests) == 1
    assert recorded_requests[0].headers['X-PB-Chatroom-Participant'] == PARTICIPANT


# ---------------------------------------------------------------------------
# Requirement 2: list_threads with no since filter
# ---------------------------------------------------------------------------


async def test_it_returns_the_list_of_threads_on_list_threads_with_no_since_filter():
    threads = [
        {'id': '1', 'subject': 'hello', 'status': 'open'},
        {'id': '2', 'subject': 'world', 'status': 'open'},
    ]
    transport = _make_transport([('GET', '/api/threads', 200, threads)])
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)
    result = await client.list_threads()
    assert result == threads


# ---------------------------------------------------------------------------
# Requirement 3: list_threads with since cursor → updated_after query param
# ---------------------------------------------------------------------------


async def test_it_filters_list_threads_results_by_since_cursor_using_the_updated_after_query_parameter(  # noqa: E501
    recorded_requests,
):
    threads = [{'id': '3', 'subject': 'newer', 'status': 'open'}]

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, json=threads)

    transport = httpx.MockTransport(handler)
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)

    since = '2024-01-01T00:00:00Z'
    result = await client.list_threads(since=since)

    assert result == threads
    assert len(recorded_requests) == 1
    assert 'updated_after=2024-01-01T00%3A00%3A00Z' in str(
        recorded_requests[0].url
    ) or 'updated_after=2024-01-01T00:00:00Z' in str(recorded_requests[0].url)


# ---------------------------------------------------------------------------
# Requirement 4: get_thread returns thread + messages
# ---------------------------------------------------------------------------


async def test_it_returns_the_thread_and_its_messages_on_get_thread():
    thread_with_messages = {
        'id': 'abc',
        'subject': 'help',
        'status': 'open',
        'messages': [{'id': 'm1', 'thread_id': 'abc', 'from_participant': 'bob', 'body': 'hi'}],
    }
    transport = _make_transport([('GET', '/api/threads/abc', 200, thread_with_messages)])
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)
    result = await client.get_thread('abc')
    assert result == thread_with_messages


# ---------------------------------------------------------------------------
# Requirement 5: post_message returns the created message id
# ---------------------------------------------------------------------------


async def test_it_posts_a_message_body_via_post_message_and_returns_the_created_message_id(
    recorded_requests,
):
    created_message = {
        'id': 'msg-99',
        'thread_id': 'abc',
        'from_participant': PARTICIPANT,
        'body': 'response text',
    }

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(201, json=created_message)

    transport = httpx.MockTransport(handler)
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)

    result = await client.post_message('abc', body='response text')

    assert result == 'msg-99'
    assert len(recorded_requests) == 1
    payload = json.loads(recorded_requests[0].content)
    assert payload['body'] == 'response text'


# ---------------------------------------------------------------------------
# Requirement 6: ack_thread returns the updated thread status
# ---------------------------------------------------------------------------


async def test_it_sends_ack_via_ack_thread_and_returns_the_updated_thread_status(
    recorded_requests,
):
    acked_thread = {'id': 'abc', 'subject': 'help', 'status': 'closed'}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, json=acked_thread)

    transport = httpx.MockTransport(handler)
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)

    result = await client.ack_thread('abc')

    assert result == acked_thread
    assert len(recorded_requests) == 1
    assert '/api/threads/abc/ack' in str(recorded_requests[0].url)


# ---------------------------------------------------------------------------
# Requirement 7: create_root_thread
# ---------------------------------------------------------------------------


async def test_it_creates_a_root_thread_with_subject_body_to_participant_and_optional_metadata_via_create_root_thread(  # noqa: E501
    recorded_requests,
):
    created_thread = {
        'id': 'new-thread-1',
        'subject': 'Task',
        'from_participant': PARTICIPANT,
        'to_participant': 'bob-auto',
        'status': 'open',
        'metadata': {'priority': 'high'},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(201, json=created_thread)

    transport = httpx.MockTransport(handler)
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)

    result = await client.create_root_thread(
        subject='Task',
        body='Please do this',
        to_participant='bob-auto',
        metadata={'priority': 'high'},
    )

    assert result == created_thread
    assert len(recorded_requests) == 1
    payload = json.loads(recorded_requests[0].content)
    assert payload['subject'] == 'Task'
    assert payload['body'] == 'Please do this'
    assert payload['to_participant'] == 'bob-auto'
    assert payload['metadata'] == {'priority': 'high'}


# ---------------------------------------------------------------------------
# Requirement 8: raises transport error on 5xx
# ---------------------------------------------------------------------------


async def test_it_raises_a_transport_error_when_the_server_returns_a_5xx():
    transport = _make_transport([('GET', '/api/threads', 500, {'detail': 'server exploded'})])
    client = ChatroomClient(base_url=BASE_URL, participant_id=PARTICIPANT, transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        await client.list_threads()

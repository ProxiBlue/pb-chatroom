"""Tests for Pydantic v2 request/response schemas."""

from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError


def test_it_accepts_a_valid_ThreadCreate_payload():
    from pb_chatroom.schemas import ThreadCreate

    tc = ThreadCreate(to='agent-b', subject='Hello', body='First message')
    assert tc.to == 'agent-b'
    assert tc.subject == 'Hello'
    assert tc.body == 'First message'


def test_it_rejects_ThreadCreate_with_empty_subject():
    from pb_chatroom.schemas import ThreadCreate

    with pytest.raises(ValidationError):
        ThreadCreate(to='agent-b', subject='', body='Some body')


def test_it_rejects_ThreadCreate_with_body_exceeding_10000_characters():
    from pb_chatroom.schemas import ThreadCreate

    with pytest.raises(ValidationError):
        ThreadCreate(to='agent-b', subject='Hello', body='x' * 10001)


def test_it_rejects_MessageCreate_with_empty_body():
    from pb_chatroom.schemas import MessageCreate

    with pytest.raises(ValidationError):
        MessageCreate(body='')


def test_it_serialises_Thread_id_as_a_string_UUID():
    from datetime import datetime
    from uuid import UUID

    from pb_chatroom.schemas import Thread

    now = datetime.now(tz=UTC)
    thread_id = UUID('12345678-1234-5678-1234-567812345678')
    t = Thread(
        id=thread_id,
        subject='Hello',
        created_by='agent-a',
        status='open',
        created_at=now,
        last_message_at=now,
    )
    data = t.model_dump(mode='json')
    assert isinstance(data['id'], str)
    assert data['id'] == '12345678-1234-5678-1234-567812345678'


def test_it_serialises_datetime_fields_as_ISO8601_UTC_with_Z_suffix():
    from datetime import datetime
    from uuid import UUID

    from pb_chatroom.schemas import Thread

    now = datetime(2024, 1, 15, 12, 30, 45, tzinfo=UTC)
    t = Thread(
        id=UUID('12345678-1234-5678-1234-567812345678'),
        subject='Hello',
        created_by='agent-a',
        status='open',
        created_at=now,
        last_message_at=now,
    )
    data = t.model_dump(mode='json')
    assert data['created_at'] == '2024-01-15T12:30:45Z'
    assert data['last_message_at'] == '2024-01-15T12:30:45Z'


def test_it_rejects_Thread_status_values_outside_the_open_acked_literal_set():
    from datetime import datetime
    from uuid import UUID

    from pb_chatroom.schemas import Thread

    now = datetime.now(tz=UTC)
    with pytest.raises(ValidationError):
        Thread(
            id=UUID('12345678-1234-5678-1234-567812345678'),
            subject='Hello',
            created_by='agent-a',
            status='closed',
            created_at=now,
            last_message_at=now,
        )

"""Messages store layer for pb-chatroom."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .errors import ThreadNotFoundError
from .schema import connect

_INSERT_MSG = (
    'INSERT INTO messages '
    '(id, thread_id, from_participant, to_participant, body, kind, metadata, created_at) '
    'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec='microseconds')


async def _assert_thread_exists(db, thread_id: str) -> None:  # type: ignore[no-untyped-def]
    async with db.execute('SELECT id FROM threads WHERE id = ?', (thread_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise ThreadNotFoundError(f'Thread {thread_id!r} not found')


async def append_message(
    db_path: Path | str,
    *,
    thread_id: str,
    from_participant: str,
    to_participant: str,
    body: str,
    metadata: dict | None = None,
) -> dict:
    """Insert a message row and update threads.last_message_at atomically."""
    msg_id = str(uuid.uuid4())
    created_at = _now_iso()
    meta_json = json.dumps(metadata if metadata is not None else {})

    async with connect(db_path) as db:
        await _assert_thread_exists(db, thread_id)
        await db.execute(
            _INSERT_MSG,
            (
                msg_id,
                thread_id,
                from_participant,
                to_participant,
                body,
                'message',
                meta_json,
                created_at,
            ),
        )
        await db.execute(
            'UPDATE threads SET last_message_at = ? WHERE id = ?',
            (created_at, thread_id),
        )
        await db.commit()

    return {
        'id': msg_id,
        'thread_id': thread_id,
        'from_participant': from_participant,
        'to_participant': to_participant,
        'body': body,
        'kind': 'message',
        'metadata': metadata if metadata is not None else {},
        'created_at': created_at,
    }


async def append_ack(
    db_path: Path | str,
    *,
    thread_id: str,
    from_participant: str,
    to_participant: str,
    body: str = 'Ack',
    metadata: dict | None = None,
) -> dict:
    """Insert an ack row, flip thread to acked, update last_message_at atomically."""
    msg_id = str(uuid.uuid4())
    created_at = _now_iso()
    meta_json = json.dumps(metadata if metadata is not None else {})

    async with connect(db_path) as db:
        await _assert_thread_exists(db, thread_id)
        await db.execute(
            _INSERT_MSG,
            (
                msg_id,
                thread_id,
                from_participant,
                to_participant,
                body,
                'ack',
                meta_json,
                created_at,
            ),
        )
        await db.execute(
            "UPDATE threads SET status = 'acked', last_message_at = ? WHERE id = ?",
            (created_at, thread_id),
        )
        await db.commit()

    return {
        'id': msg_id,
        'thread_id': thread_id,
        'from_participant': from_participant,
        'to_participant': to_participant,
        'body': body,
        'kind': 'ack',
        'metadata': metadata if metadata is not None else {},
        'created_at': created_at,
    }


async def list_messages(db_path: Path | str, thread_id: str) -> list[dict]:
    """Return all messages for thread_id ordered by created_at ASC."""
    async with connect(db_path) as db, db.execute(
        'SELECT id, thread_id, from_participant, to_participant, '
        'body, kind, metadata, created_at '
        'FROM messages WHERE thread_id = ? ORDER BY created_at ASC',
        (thread_id,),
    ) as cur:
        columns = [col[0] for col in cur.description]  # type: ignore[union-attr]
        raw_rows = await cur.fetchall()

    result = []
    for row in raw_rows:
        d = dict(zip(columns, row, strict=True))
        d['metadata'] = json.loads(d['metadata'])
        result.append(d)
    return result

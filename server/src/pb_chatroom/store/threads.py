"""Threads store — async CRUD over the threads table."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .schema import connect


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


async def create_thread(
    db_path: Path | str,
    *,
    subject: str,
    created_by: str,
    to_participant: str,
    body: str,
) -> dict:
    thread_id = str(uuid.uuid4())
    now = _now_utc()
    async with connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO threads (id, subject, created_by, status, created_at, last_message_at)
            VALUES (?, ?, ?, 'open', ?, ?)
            """,
            (thread_id, subject, created_by, now, now),
        )
        msg_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO messages (id, thread_id, from_participant, to_participant,
                                  body, kind, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, 'message', '{}', ?)
            """,
            (msg_id, thread_id, created_by, to_participant, body, now),
        )
        await db.commit()
    return {
        'id': thread_id,
        'subject': subject,
        'created_by': created_by,
        'status': 'open',
        'created_at': now,
        'last_message_at': now,
    }


async def list_threads(
    db_path: Path | str,
    *,
    to_participant: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List threads with status-grouped + recency ordering.

    Open threads come first, then acked. Within each group, most recently
    active wins. The returned dict carries the ROOT message's recipient
    (`to_participant` — i.e. who the thread was opened for) and a
    `message_count` so the dashboard can render at-a-glance summary rows.
    """
    clauses: list[str] = []
    params: list[str] = []
    if to_participant is not None:
        # Filter by "thread has at least one message addressed to X" — covers
        # both the root recipient and any later replies. The displayed
        # `to_participant` field is always the ROOT recipient (subquery below).
        clauses.append(
            't.id IN (SELECT thread_id FROM messages WHERE to_participant = ?)'
        )
        params.append(to_participant)
    if status is not None:
        clauses.append('t.status = ?')
        params.append(status)

    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    sql = f"""
        SELECT t.id, t.subject, t.created_by, t.status,
               t.created_at, t.last_message_at,
               (SELECT to_participant FROM messages
                WHERE thread_id = t.id
                ORDER BY created_at ASC LIMIT 1) AS root_to_participant,
               (SELECT COUNT(*) FROM messages WHERE thread_id = t.id) AS message_count
        FROM threads t
        {where}
        ORDER BY
            CASE t.status WHEN 'open' THEN 0 ELSE 1 END,
            t.last_message_at DESC
    """
    async with connect(db_path) as db:
        db.row_factory = None
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
    return [
        {
            'id': r[0],
            'subject': r[1],
            'created_by': r[2],
            'status': r[3],
            'created_at': r[4],
            'last_message_at': r[5],
            'to_participant': r[6],
            'message_count': r[7],
        }
        for r in rows
    ]


_THREAD_SELECT = (
    'SELECT id, subject, created_by, status, created_at, last_message_at'
    ' FROM threads WHERE id = ?'
)


async def get_thread(db_path: Path | str, thread_id: str) -> dict | None:
    async with connect(db_path) as db:
        cursor = await db.execute(_THREAD_SELECT, (thread_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return {
        'id': row[0],
        'subject': row[1],
        'created_by': row[2],
        'status': row[3],
        'created_at': row[4],
        'last_message_at': row[5],
    }


async def get_thread_with_messages(db_path: Path | str, thread_id: str) -> dict | None:
    async with connect(db_path) as db:
        t_cursor = await db.execute(_THREAD_SELECT, (thread_id,))
        t_row = await t_cursor.fetchone()
        if t_row is None:
            return None
        m_cursor = await db.execute(
            """
            SELECT id, thread_id, from_participant, to_participant, body, kind, metadata, created_at
            FROM messages
            WHERE thread_id = ?
            ORDER BY created_at ASC
            """,
            (thread_id,),
        )
        m_rows = await m_cursor.fetchall()
    messages = [
        {
            'id': m[0],
            'thread_id': m[1],
            'from_participant': m[2],
            'to_participant': m[3],
            'body': m[4],
            'kind': m[5],
            'metadata': json.loads(m[6]) if isinstance(m[6], str) else (m[6] or {}),
            'created_at': m[7],
        }
        for m in m_rows
    ]
    return {
        'id': t_row[0],
        'subject': t_row[1],
        'created_by': t_row[2],
        'status': t_row[3],
        'created_at': t_row[4],
        'last_message_at': t_row[5],
        'messages': messages,
    }


async def update_thread_status(db_path: Path | str, thread_id: str, status: str) -> None:
    async with connect(db_path) as db:
        await db.execute('UPDATE threads SET status = ? WHERE id = ?', (status, thread_id))
        await db.commit()


async def touch_last_message_at(db_path: Path | str, thread_id: str, timestamp: str) -> None:
    pass

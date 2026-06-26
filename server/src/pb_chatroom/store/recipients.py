"""Multi-recipient CRUD for pb-chatroom thread_recipients table."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .schema import connect


def _now_utc() -> str:
    return datetime.now(UTC).isoformat().replace('+00:00', 'Z')


async def add_recipient(db_path: Path | str, thread_id: str, *, participant_id: str) -> None:
    async with connect(db_path) as db:
        await db.execute(
            'INSERT OR IGNORE INTO thread_recipients (thread_id, participant_id) VALUES (?, ?)',
            (thread_id, participant_id),
        )
        await db.commit()


async def list_recipients(db_path: Path | str, thread_id: str) -> list[dict]:
    async with connect(db_path) as db:
        cursor = await db.execute(
            'SELECT thread_id, participant_id, acked_at FROM thread_recipients WHERE thread_id = ?',
            (thread_id,),
        )
        rows = await cursor.fetchall()
    return [{'thread_id': r[0], 'participant_id': r[1], 'acked_at': r[2]} for r in rows]


async def mark_recipient_acked(
    db_path: Path | str, thread_id: str, *, participant_id: str
) -> None:
    now = _now_utc()
    async with connect(db_path) as db:
        await db.execute(
            'UPDATE thread_recipients SET acked_at = ? WHERE thread_id = ? AND participant_id = ?',
            (now, thread_id, participant_id),
        )
        await db.commit()


async def all_recipients_acked(db_path: Path | str, thread_id: str) -> bool:
    async with connect(db_path) as db:
        cursor = await db.execute(
            'SELECT COUNT(*) FROM thread_recipients WHERE thread_id = ? AND acked_at IS NULL',
            (thread_id,),
        )
        row = await cursor.fetchone()
    return row is not None and row[0] == 0

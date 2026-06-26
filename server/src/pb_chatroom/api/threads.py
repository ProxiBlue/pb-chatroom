"""Thread REST endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..identity import _validate
from ..schemas import (
    ClaimRequest,
    ClaimResponse,
    Message,
    MessageCreate,
    Thread,
    ThreadCreate,
    ThreadWithMessages,
)
from ..store.errors import ClaimConflictError, ThreadNotFoundError
from ..store.messages import append_ack, append_message
from ..store.recipients import (
    add_recipient,
    all_recipients_acked,
    list_recipients,
    mark_recipient_acked,
)
from ..store.threads import (
    create_thread,
    get_thread_with_messages,
    list_threads,
    set_claim,
    set_discussion_type,
    update_thread_status,
)

router = APIRouter(prefix='/api/threads')


def _resolve_participant(x_pb_chatroom_participant: str | None) -> str:
    if not x_pb_chatroom_participant:
        raise HTTPException(status_code=400, detail='X-PB-Chatroom-Participant header required')
    try:
        return _validate(x_pb_chatroom_participant)
    except ValueError:
        raise HTTPException(status_code=400, detail='invalid participant id') from None


@router.post('', status_code=201)
async def post_thread(
    request: Request,
    payload: ThreadCreate,
    x_pb_chatroom_participant: str | None = Header(default=None),
):
    participant = _resolve_participant(x_pb_chatroom_participant)
    db_path = request.app.state.db_path

    # Determine primary recipient (back-compat: `to` wins; else first of list)
    primary = payload.to or payload.to_participants[0]
    extras = payload.to_participants[1:] if payload.to_participants else []

    result = await create_thread(
        db_path,
        subject=payload.subject,
        created_by=participant,
        to_participant=primary,
        body=payload.body,
    )

    if payload.discussion_type:
        await set_discussion_type(db_path, result['id'], payload.discussion_type)
        result['discussion_type'] = payload.discussion_type

    all_recipients = [primary] + extras
    for recipient in all_recipients:
        await add_recipient(db_path, result['id'], participant_id=recipient)

    result['recipients'] = all_recipients
    return JSONResponse(content=result, status_code=201)


@router.get('', response_model=list[Thread])
async def get_threads(
    request: Request,
    to: str | None = None,
    status: Literal['open', 'acked'] | None = None,
    discussion_types: str | None = None,
    since: str | None = None,
):
    db_path = request.app.state.db_path
    dt_list = [d.strip() for d in discussion_types.split(',')] if discussion_types else None
    threads = await list_threads(
        db_path, to_participant=to, status=status, discussion_types=dt_list, since=since
    )
    return threads


@router.get('/{thread_id}', response_model=ThreadWithMessages)
async def get_thread(request: Request, thread_id: str):
    db_path = request.app.state.db_path
    result = await get_thread_with_messages(db_path, thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail='thread not found')
    return result


def _resolve_participants(
    thread: dict, caller: str, extra_recipients: list[str] | None = None
) -> str:
    """Return the recipient for a reply, or raise 403 if caller is not a participant."""
    created_by = thread['created_by']
    # Seed message is always the first message; to_participant comes from it.
    seed = thread['messages'][0]
    to_participant = seed['to_participant']
    if caller == created_by:
        return to_participant
    if caller == to_participant:
        return created_by
    # Also allow thread_recipients members — they reply to the thread creator
    if extra_recipients and caller in extra_recipients:
        return created_by
    raise HTTPException(status_code=403, detail='caller is not a participant of this thread')


@router.post('/{thread_id}/messages', status_code=201, response_model=Message)
async def post_message(
    request: Request,
    thread_id: str,
    payload: MessageCreate,
    x_pb_chatroom_participant: str | None = Header(default=None),
):
    caller = _resolve_participant(x_pb_chatroom_participant)
    db_path = request.app.state.db_path
    thread = await get_thread_with_messages(db_path, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail='thread not found')
    extra_recipients = [r['participant_id'] for r in await list_recipients(db_path, thread_id)]
    recipient = _resolve_participants(thread, caller, extra_recipients)
    try:
        result = await append_message(
            db_path,
            thread_id=thread_id,
            from_participant=caller,
            to_participant=recipient,
            body=payload.body,
        )
    except ThreadNotFoundError:
        raise HTTPException(status_code=404, detail='thread not found') from None
    if payload.discussion_type:
        await set_discussion_type(db_path, thread_id, payload.discussion_type)
    return JSONResponse(content=result, status_code=201)


@router.post('/{thread_id}/claim', status_code=200, response_model=ClaimResponse)
async def post_claim(
    request: Request,
    thread_id: str,
    payload: ClaimRequest,
    x_pb_chatroom_participant: str | None = Header(default=None),
):
    caller = _resolve_participant(x_pb_chatroom_participant)
    db_path = request.app.state.db_path
    try:
        result = await set_claim(
            db_path, thread_id=thread_id, participant_id=caller, scope=payload.scope
        )
    except ClaimConflictError as e:
        raise HTTPException(status_code=409, detail={'claimed_by': e.claimed_by}) from e
    except ThreadNotFoundError:
        raise HTTPException(status_code=404, detail='thread not found') from None
    return result


@router.post('/{thread_id}/ack', status_code=200, response_model=Message)
async def post_ack(
    request: Request,
    thread_id: str,
    payload: MessageCreate | None = None,
    x_pb_chatroom_participant: str | None = Header(default=None),
):
    caller = _resolve_participant(x_pb_chatroom_participant)
    db_path = request.app.state.db_path
    thread = await get_thread_with_messages(db_path, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail='thread not found')
    extra_recipients = await list_recipients(db_path, thread_id)
    extra_ids = [r['participant_id'] for r in extra_recipients]
    recipient = _resolve_participants(thread, caller, extra_ids)
    body = payload.body if payload is not None else 'Ack'

    caller_in_recipients = caller in extra_ids
    if caller_in_recipients:
        # Multi-recipient path: insert ack message without flipping thread status yet
        import uuid

        from ..store.messages import _INSERT_MSG, _assert_thread_exists, _now_iso
        from ..store.schema import connect

        msg_id = str(uuid.uuid4())
        created_at = _now_iso()
        async with connect(db_path) as db:
            await _assert_thread_exists(db, thread_id)
            await db.execute(
                _INSERT_MSG,
                (msg_id, thread_id, caller, recipient, body, 'ack', '{}', created_at),
            )
            await db.execute(
                'UPDATE threads SET last_message_at = ? WHERE id = ?',
                (created_at, thread_id),
            )
            await db.commit()

        await mark_recipient_acked(db_path, thread_id, participant_id=caller)
        if await all_recipients_acked(db_path, thread_id):
            await update_thread_status(db_path, thread_id, 'acked')

        return {
            'id': msg_id,
            'thread_id': thread_id,
            'from_participant': caller,
            'to_participant': recipient,
            'body': body,
            'kind': 'ack',
            'metadata': {},
            'created_at': created_at,
        }

    # Single-recipient (original) path — flips thread status immediately via append_ack
    try:
        result = await append_ack(
            db_path,
            thread_id=thread_id,
            from_participant=caller,
            to_participant=recipient,
            body=body,
        )
    except ThreadNotFoundError:
        raise HTTPException(status_code=404, detail='thread not found') from None
    return result

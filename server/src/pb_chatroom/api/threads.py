"""Thread REST endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..identity import _validate
from ..schemas import Message, MessageCreate, Thread, ThreadCreate, ThreadWithMessages
from ..store.errors import ThreadNotFoundError
from ..store.messages import append_ack, append_message
from ..store.threads import create_thread, get_thread_with_messages, list_threads

router = APIRouter(prefix='/api/threads')


def _resolve_participant(x_pb_chatroom_participant: str | None) -> str:
    if not x_pb_chatroom_participant:
        raise HTTPException(status_code=400, detail='X-PB-Chatroom-Participant header required')
    try:
        return _validate(x_pb_chatroom_participant)
    except ValueError:
        raise HTTPException(status_code=400, detail='invalid participant id') from None


@router.post('', status_code=201, response_model=Thread)
async def post_thread(
    request: Request,
    payload: ThreadCreate,
    x_pb_chatroom_participant: str | None = Header(default=None),
):
    participant = _resolve_participant(x_pb_chatroom_participant)
    db_path = request.app.state.db_path
    result = await create_thread(
        db_path,
        subject=payload.subject,
        created_by=participant,
        to_participant=payload.to,
        body=payload.body,
    )
    return JSONResponse(content=result, status_code=201)


@router.get('', response_model=list[Thread])
async def get_threads(
    request: Request,
    to: str | None = None,
    status: Literal['open', 'acked'] | None = None,
):
    db_path = request.app.state.db_path
    threads = await list_threads(db_path, to_participant=to, status=status)
    return threads


@router.get('/{thread_id}', response_model=ThreadWithMessages)
async def get_thread(request: Request, thread_id: str):
    db_path = request.app.state.db_path
    result = await get_thread_with_messages(db_path, thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail='thread not found')
    return result


def _resolve_participants(thread: dict, caller: str) -> str:
    """Return the recipient for a reply, or raise 403 if caller is not a participant."""
    created_by = thread['created_by']
    # Seed message is always the first message; to_participant comes from it.
    seed = thread['messages'][0]
    to_participant = seed['to_participant']
    if caller == created_by:
        return to_participant
    if caller == to_participant:
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
    recipient = _resolve_participants(thread, caller)
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
    return JSONResponse(content=result, status_code=201)


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
    recipient = _resolve_participants(thread, caller)
    body = payload.body if payload is not None else 'Ack'
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

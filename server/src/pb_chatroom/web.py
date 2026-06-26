"""HTML dashboard routes for pb-chatroom."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .store.messages import has_legacy_identity_in_last_n_days
from .store.threads import get_thread_with_messages, list_threads

templates = Jinja2Templates(directory=Path(__file__).parent / 'templates')

router = APIRouter()


def _base_context(request: Request) -> dict:
    """Context fields every dashboard template needs (shared via base.html)."""
    return {'refresh_interval_seconds': request.app.state.settings.refresh_interval_seconds}


@router.get('/', response_class=HTMLResponse)
async def threads_list(request: Request) -> HTMLResponse:
    db_path = request.app.state.settings.db_path
    threads = await list_threads(db_path)
    show_legacy_warning = await has_legacy_identity_in_last_n_days(db_path)

    escalations = await list_threads(db_path, discussion_types=['escalation'], status='open')
    postmortems = await list_threads(db_path, discussion_types=['postmortem'], status='open')
    open_threads = await list_threads(db_path, status='open')
    active_claims = [t for t in open_threads if t.get('claimed_by')]

    return templates.TemplateResponse(
        request,
        'threads_list.html',
        {
            **_base_context(request),
            'threads': threads,
            'show_legacy_warning': show_legacy_warning,
            'escalation_count': len(escalations),
            'postmortem_count': len(postmortems),
            'active_claims': active_claims,
        },
    )


@router.get('/threads/{thread_id}', response_class=HTMLResponse)
async def thread_detail(request: Request, thread_id: str) -> HTMLResponse:
    db_path = request.app.state.settings.db_path
    data = await get_thread_with_messages(db_path, thread_id)
    if data is None:
        return HTMLResponse(status_code=404, content='Thread not found')
    thread = {k: v for k, v in data.items() if k != 'messages'}
    messages = data['messages']
    return templates.TemplateResponse(
        request,
        'thread_detail.html',
        {**_base_context(request), 'thread': thread, 'messages': messages},
    )

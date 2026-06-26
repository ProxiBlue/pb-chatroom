"""Pydantic v2 request/response models for the pb-chatroom REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

DISCUSSION_TYPES = (
    'claim_request',
    'claim_accepted',
    'design_question',
    'debate',
    'postmortem',
    'escalation',
)


class ThreadCreate(BaseModel):
    to: str | None = None
    to_participants: list[str] = Field(default_factory=list)
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    discussion_type: str | None = None
    metadata: dict | None = None

    @model_validator(mode='after')
    def at_least_one_recipient(self) -> ThreadCreate:
        if not self.to and not self.to_participants:
            raise ValueError('to or to_participants is required')
        return self

    @model_validator(mode='after')
    def valid_discussion_type(self) -> ThreadCreate:
        if self.discussion_type and self.discussion_type not in DISCUSSION_TYPES:
            raise ValueError(f'invalid discussion_type: {self.discussion_type!r}')
        return self


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    discussion_type: str | None = None

    @model_validator(mode='after')
    def valid_discussion_type(self) -> MessageCreate:
        if self.discussion_type and self.discussion_type not in DISCUSSION_TYPES:
            raise ValueError(f'invalid discussion_type: {self.discussion_type!r}')
        return self


class Thread(BaseModel):
    id: UUID
    subject: str
    created_by: str
    status: Literal['open', 'acked']
    created_at: datetime
    last_message_at: datetime
    discussion_type: str | None = None
    claimed_by: str | None = None
    claimed_at: str | None = None
    claim_scope: str | None = None
    recipients: list[str] = Field(default_factory=list)


class Message(BaseModel):
    id: UUID
    thread_id: UUID
    from_participant: str
    to_participant: str
    body: str
    kind: Literal['message', 'ack']
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ThreadWithMessages(Thread):
    messages: list[Message] = Field(default_factory=list)


class ClaimRequest(BaseModel):
    scope: str = Field(..., min_length=1, max_length=500)


class ClaimResponse(BaseModel):
    claimed_by: str
    claimed_at: str
    claim_scope: str

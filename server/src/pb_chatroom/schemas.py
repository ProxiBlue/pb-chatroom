"""Pydantic v2 request/response models for the pb-chatroom REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    to: str
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class Thread(BaseModel):
    id: UUID
    subject: str
    created_by: str
    status: Literal['open', 'acked']
    created_at: datetime
    last_message_at: datetime


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

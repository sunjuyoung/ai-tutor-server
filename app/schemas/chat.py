import uuid
from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    persona_id: uuid.UUID
    scenario_id: uuid.UUID


class ConversationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    persona_id: uuid.UUID
    scenario_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_sec: int | None
    message_count: int


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str

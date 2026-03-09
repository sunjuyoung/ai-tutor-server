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


class ConversationDetailRead(BaseModel):
    """
    대화 상세 응답 — 페르소나/시나리오 메타데이터 포함.

    '대화 이어하기' 기능에서 사용. 프론트엔드가 채팅 UI 헤더를
    복원하는 데 필요한 페르소나/시나리오 이름과 이모지를 포함한다.
    """
    id: str
    user_id: str
    persona_id: str
    scenario_id: str
    started_at: str | None
    ended_at: str | None
    message_count: int
    duration_sec: int | None
    # 프론트엔드 채팅 헤더 복원용
    persona_name: str
    persona_emoji: str
    scenario_title: str
    scenario_emoji: str

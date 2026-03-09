import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Persona(SQLModel, table=True):
    __tablename__ = "personas"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50)
    language: str = Field(max_length=10)  # en | ja
    personality_prompt: str  # system prompt template
    is_premium: bool = Field(default=False)
    fallback_responses: list | None = Field(default=None, sa_column=Column(JSONB))
    age: int | None = None
    job: str | None = Field(default=None, max_length=100)
    personality: str | None = Field(default=None, max_length=200)
    speech_style: str | None = Field(default=None, max_length=200)
    icon_emoji: str = Field(default="🤖", max_length=10)
    intro_line: str | None = Field(default=None, max_length=200)
    # Phase 3.5: TTS 음성 (alloy|echo|fable|onyx|nova|shimmer)
    tts_voice: str = Field(default="nova", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)

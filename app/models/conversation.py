import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    persona_id: uuid.UUID = Field(foreign_key="personas.id")
    scenario_id: uuid.UUID = Field(foreign_key="scenarios.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    duration_sec: int | None = None
    message_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

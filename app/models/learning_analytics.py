import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class LearningAnalytics(SQLModel, table=True):
    __tablename__ = "learning_analytics"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    corrections: list | None = Field(default=None, sa_column=Column(JSONB))
    new_expressions: list | None = Field(default=None, sa_column=Column(JSONB))
    fluency_score: int | None = None
    summary: str | None = None
    status: str = Field(default="pending", max_length=20)  # pending | processing | completed | failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

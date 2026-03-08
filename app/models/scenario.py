import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Scenario(SQLModel, table=True):
    __tablename__ = "scenarios"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    persona_id: uuid.UUID = Field(foreign_key="personas.id", index=True)
    title: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=100)
    situation: str | None = Field(default=None, max_length=300)
    goal: str | None = Field(default=None, max_length=300)
    difficulty: int = Field(default=1)  # 1-3
    estimated_minutes: int = Field(default=10)
    is_premium: bool = Field(default=False)
    icon_emoji: str = Field(default="💬", max_length=10)
    background_color: str = Field(default="#F8F9FA", max_length=10)
    created_at: datetime = Field(default_factory=datetime.utcnow)

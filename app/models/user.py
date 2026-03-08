import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str | None = None
    nickname: str | None = Field(default=None, max_length=50)
    target_language: str | None = Field(default=None, max_length=10)  # en | ja
    learning_purpose: str | None = Field(default=None, max_length=30)  # travel | work | daily | exam
    is_onboarded: bool = Field(default=False)
    level: int = Field(default=1)
    xp: int = Field(default=0)
    streak_days: int = Field(default=0)
    plan_type: str = Field(default="FREE", max_length=20)  # FREE | PRO | ENTERPRISE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    role: str = Field(max_length=20)  # user | assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

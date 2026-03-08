import uuid

from pydantic import BaseModel


class PersonaRead(BaseModel):
    id: uuid.UUID
    name: str
    language: str
    is_premium: bool
    age: int | None
    job: str | None
    personality: str | None
    speech_style: str | None
    icon_emoji: str
    intro_line: str | None


class ScenarioRead(BaseModel):
    id: uuid.UUID
    persona_id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    situation: str | None
    goal: str | None
    difficulty: int
    estimated_minutes: int
    is_premium: bool
    icon_emoji: str
    background_color: str


class PersonaDetailRead(PersonaRead):
    scenarios: list[ScenarioRead] = []

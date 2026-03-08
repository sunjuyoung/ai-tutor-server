import uuid

from pydantic import BaseModel


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    nickname: str | None
    target_language: str | None
    learning_purpose: str | None
    is_onboarded: bool
    level: int
    xp: int
    streak_days: int
    plan_type: str


class UserUpdate(BaseModel):
    nickname: str | None = None


class OnboardingRequest(BaseModel):
    target_language: str
    learning_purpose: str
    nickname: str

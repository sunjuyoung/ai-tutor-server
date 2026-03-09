import uuid
from datetime import datetime

from pydantic import BaseModel


class CorrectionItem(BaseModel):
    original: str
    corrected: str
    error_type: str  # grammar | vocabulary | expression
    explanation: str
    frequency_hint: int = 1


class NewExpressionItem(BaseModel):
    expression: str
    meaning_ko: str
    context: str


class CorrectionReport(BaseModel):
    corrections: list[CorrectionItem] = []
    new_expressions: list[NewExpressionItem] = []
    fluency_score: int = 50
    summary: str = ""


class ReportRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    corrections: list[CorrectionItem] | None
    new_expressions: list[NewExpressionItem] | None
    fluency_score: int | None
    summary: str | None
    status: str
    created_at: datetime
    completed_at: datetime | None

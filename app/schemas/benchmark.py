"""
벤치마크 스키마 — Before/After 비교 요청/응답

Phase 3 (W14): Before/After 학습 효과 측정
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BenchmarkRead(BaseModel):
    """벤치마크 단건 응답"""
    id: uuid.UUID
    scenario_id: uuid.UUID
    conversation_id: uuid.UUID
    round_number: int
    grammar_errors: int
    new_expressions: int
    hint_count: int
    fluency_score: int | None
    response_time_avg: float | None
    persona_comment: str | None
    created_at: datetime


class BenchmarkCompareResponse(BaseModel):
    """Before/After 비교 응답"""
    scenario_id: uuid.UUID
    scenario_title: str
    scenario_emoji: str
    persona_name: str
    rounds: list[BenchmarkRead]
    # 성장 요약 (첫 라운드 vs 최신 라운드)
    improvement: dict | None = None


class BenchmarkReminderItem(BaseModel):
    """홈 화면 재도전 알림용"""
    scenario_id: uuid.UUID
    scenario_title: str
    scenario_emoji: str
    persona_name: str
    days_since_last: int
    last_fluency_score: int | None

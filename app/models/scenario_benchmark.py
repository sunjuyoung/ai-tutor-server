"""
시나리오 벤치마크 모델 — Before/After 성장 측정

Phase 3 (W14) Before/After 학습 효과 측정:
- 동일 시나리오를 벤치마크 모드로 재도전하면 이전 기록과 비교
- 라운드별 점수(문법 오류, 새 표현, 힌트 사용, 유창성)를 저장
- 14일 경과 시나리오는 홈 화면에서 재도전 알림 표시
"""

import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ScenarioBenchmark(SQLModel, table=True):
    __tablename__ = "scenario_benchmarks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    scenario_id: uuid.UUID = Field(foreign_key="scenarios.id", index=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id")

    # 라운드 번호 (1 = 첫 도전, 2 = 재도전, ...)
    round_number: int = Field(default=1)

    # 측정 지표
    grammar_errors: int = Field(default=0)       # 문법 오류 수
    new_expressions: int = Field(default=0)      # 새 표현 사용 수
    hint_count: int = Field(default=0)           # 힌트 사용 횟수
    fluency_score: int | None = None             # 유창성 점수 (0~100)
    response_time_avg: float | None = None       # 평균 응답 시간 (초)

    # 상세 데이터 (JSON으로 확장 가능)
    details: dict | None = Field(default=None, sa_column=Column(JSONB))

    # 페르소나 코멘트 (LLM 생성)
    persona_comment: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

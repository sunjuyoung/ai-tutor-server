"""
Waitlist 모델 — 베타 대기 리스트 + 레퍼럴 시스템

Phase 3 (W15) Waitlist + 텍스트 데모:
- 이메일, 관심 언어, 학습 상황 수집
- 레퍼럴 코드 → 초대 수에 따른 우선순위 조정
- 베타 초대 상태 관리 (pending → invited → joined)
"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class WaitlistEntry(SQLModel, table=True):
    __tablename__ = "waitlist"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)

    # 관심 언어 (쉼표 구분: "en", "ja", "en,ja")
    interested_languages: str | None = Field(default=None, max_length=20)
    # 가장 해보고 싶은 상황
    interested_situation: str | None = Field(default=None, max_length=50)

    # 레퍼럴 시스템
    referral_code: str = Field(unique=True, index=True, max_length=20)
    referred_by: str | None = Field(default=None, max_length=20)  # 초대한 사람의 referral_code
    referral_count: int = Field(default=0)  # 이 코드로 가입한 사람 수

    # 대기 순번 (가입 순서)
    queue_position: int = Field(default=0)

    # 상태: pending(대기) | invited(초대됨) | joined(가입완료)
    status: str = Field(default="pending", max_length=20)

    created_at: datetime = Field(default_factory=datetime.utcnow)

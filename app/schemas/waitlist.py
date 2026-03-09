"""
Waitlist 스키마 — 대기 리스트 요청/응답

Phase 3 (W15): Waitlist + 텍스트 데모
"""

from pydantic import BaseModel, EmailStr


class WaitlistRegisterRequest(BaseModel):
    """Waitlist 등록 요청"""
    email: EmailStr
    interested_languages: str | None = None  # "en", "ja", "en,ja"
    interested_situation: str | None = None   # 관심 상황
    referred_by: str | None = None            # 추천인 referral_code


class WaitlistRegisterResponse(BaseModel):
    """Waitlist 등록 응답"""
    queue_position: int       # 대기 순번
    referral_code: str        # 내 추천 코드
    total_waitlist: int       # 전체 대기자 수


class WaitlistStatusResponse(BaseModel):
    """Waitlist 현황 (공개 정보)"""
    total_count: int

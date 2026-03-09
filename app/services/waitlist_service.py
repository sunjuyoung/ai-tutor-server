"""
Waitlist 서비스 — 대기 리스트 관리 + 레퍼럴

Phase 3 (W15) 핵심 기능:
1. 이메일 등록 + 레퍼럴 코드 생성
2. 레퍼럴 카운트 증가 (추천인 우선순위 상승)
3. 대기 현황 조회
4. 베타 초대 이메일 발송 (stub)
"""

import logging
import secrets
import string
import uuid

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.waitlist import WaitlistEntry

logger = logging.getLogger(__name__)


def _generate_referral_code(length: int = 8) -> str:
    """랜덤 레퍼럴 코드 생성 (영문 대문자 + 숫자)"""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


async def register(
    email: str,
    interested_languages: str | None,
    interested_situation: str | None,
    referred_by: str | None,
    session: AsyncSession,
) -> dict:
    """
    Waitlist 등록.

    Returns:
        { queue_position, referral_code, total_waitlist }

    Raises:
        ValueError: 이미 등록된 이메일
    """
    # 중복 이메일 체크
    existing = await session.execute(
        select(WaitlistEntry).where(WaitlistEntry.email == email)
    )
    if existing.scalar_one_or_none():
        raise ValueError("이미 등록된 이메일입니다.")

    # 현재 대기자 수 (= 다음 순번)
    count_result = await session.execute(select(func.count(WaitlistEntry.id)))
    total = count_result.scalar() or 0
    queue_position = total + 1

    # 레퍼럴 코드 생성 (유니크 보장)
    referral_code = _generate_referral_code()
    while True:
        code_check = await session.execute(
            select(WaitlistEntry).where(WaitlistEntry.referral_code == referral_code)
        )
        if not code_check.scalar_one_or_none():
            break
        referral_code = _generate_referral_code()

    # 등록
    entry = WaitlistEntry(
        email=email,
        interested_languages=interested_languages,
        interested_situation=interested_situation,
        referral_code=referral_code,
        referred_by=referred_by,
        queue_position=queue_position,
    )
    session.add(entry)

    # 추천인 referral_count 증가
    if referred_by:
        referrer_result = await session.execute(
            select(WaitlistEntry).where(WaitlistEntry.referral_code == referred_by)
        )
        referrer = referrer_result.scalar_one_or_none()
        if referrer:
            referrer.referral_count += 1
            logger.info("레퍼럴 카운트 증가: %s → %d", referred_by, referrer.referral_count)

    await session.commit()
    await session.refresh(entry)

    logger.info("Waitlist 등록: %s (순번 %d)", email, queue_position)

    return {
        "queue_position": queue_position,
        "referral_code": referral_code,
        "total_waitlist": queue_position,  # 등록 직후이므로 total = position
    }


async def get_total_count(session: AsyncSession) -> int:
    """전체 대기자 수 조회"""
    result = await session.execute(select(func.count(WaitlistEntry.id)))
    return result.scalar() or 0


async def send_beta_invite(email: str) -> bool:
    """
    베타 초대 이메일 발송 (stub).

    TODO: SendGrid 또는 AWS SES 연동
    현재는 로그만 남기고 True 반환.
    """
    logger.info("[STUB] 베타 초대 이메일 발송: %s", email)
    return True

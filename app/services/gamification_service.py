"""
게이미피케이션 서비스 — XP, 레벨, 스트릭 관리

핵심 메커니즘:
- XP(경험치): 대화 시간(분) × 20 XP 기본 보상, 힌트 사용 시 50% 감소
- Level: 누적 XP 임계값 기반 10단계 레벨링 시스템
- Streak: 연속 학습 일수 추적 (매일 1회 대화 완료 시 유지)
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.redis import get_redis
from app.models.conversation import Conversation
from app.models.user import User

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 레벨 시스템 상수
# 레벨별 누적 XP 임계값 (index = level)
# Level 1: 0 XP, Level 2: 300 XP, ..., Level 10: 16000 XP
# ──────────────────────────────────────────────
LEVEL_THRESHOLDS = [0, 300, 800, 1500, 2500, 4000, 6000, 8500, 12000, 16000]

# XP 계산 상수
XP_PER_MINUTE = 20         # 대화 1분당 기본 XP
MIN_XP = 10                # 최소 보장 XP (아주 짧은 대화라도 보상)
HINT_PENALTY = 0.5         # 힌트 1회당 XP 감소 비율 (50%)
MAX_HINT_PENALTY_RATIO = 0.8  # 힌트 패널티 상한 (최대 80% 감소)


def calculate_xp(duration_sec: int, hint_count: int = 0) -> int:
    """
    대화 기반 XP 계산.

    Args:
        duration_sec: 대화 총 시간 (초)
        hint_count: 사용한 힌트 횟수

    Returns:
        획득 XP (최소 MIN_XP 보장)

    계산 방식:
        base_xp = (대화 시간 분) × XP_PER_MINUTE
        penalty = min(hint_count × HINT_PENALTY, MAX_HINT_PENALTY_RATIO)
        final_xp = base_xp × (1 - penalty)
    """
    if duration_sec <= 0:
        return MIN_XP

    # 분 단위로 변환 (소수점 허용)
    minutes = duration_sec / 60.0
    base_xp = int(minutes * XP_PER_MINUTE)

    # 힌트 패널티 적용: 힌트 1회당 50% 감소, 최대 80%까지
    if hint_count > 0:
        penalty_ratio = min(hint_count * HINT_PENALTY, MAX_HINT_PENALTY_RATIO)
        base_xp = int(base_xp * (1.0 - penalty_ratio))

    # 최소 XP 보장
    return max(base_xp, MIN_XP)


def calculate_level(total_xp: int) -> int:
    """
    누적 XP로부터 현재 레벨 계산.

    LEVEL_THRESHOLDS를 역순으로 탐색하여
    total_xp >= threshold인 첫 번째 레벨을 반환.

    Returns:
        레벨 (1~10), 최대 레벨 10
    """
    for level in range(len(LEVEL_THRESHOLDS), 0, -1):
        if total_xp >= LEVEL_THRESHOLDS[level - 1]:
            return level
    return 1


def xp_to_next_level(total_xp: int) -> int | None:
    """
    다음 레벨까지 필요한 잔여 XP.

    Returns:
        필요 XP, 또는 최대 레벨이면 None
    """
    current_level = calculate_level(total_xp)
    if current_level >= len(LEVEL_THRESHOLDS):
        return None  # 최대 레벨 도달
    next_threshold = LEVEL_THRESHOLDS[current_level]
    return next_threshold - total_xp


async def award_xp(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """
    대화 종료 시 XP를 부여하고 레벨업 여부를 반환.

    흐름:
    1. conversation에서 duration_sec, hint_count 조회
    2. XP 계산
    3. user.xp에 누적
    4. 레벨 재계산 → 레벨업 확인
    5. DB 커밋

    Returns:
        {
            "earned_xp": 획득 XP,
            "total_xp": 누적 XP,
            "level": 현재 레벨,
            "leveled_up": 레벨업 여부,
            "xp_to_next": 다음 레벨까지 잔여 XP (None이면 최대 레벨)
        }
    """
    # 대화 정보 조회
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        logger.warning("Conversation %s not found for XP award", conversation_id)
        return {"earned_xp": 0, "total_xp": 0, "level": 1, "leveled_up": False, "xp_to_next": 300}

    # XP 계산
    earned_xp = calculate_xp(conv.duration_sec or 0, conv.hint_count)

    # 유저 조회 및 XP 적용
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    old_level = calculate_level(user.xp or 0)
    user.xp = (user.xp or 0) + earned_xp
    new_level = calculate_level(user.xp)

    # 레벨업 시 user.level 필드도 업데이트
    if new_level > old_level:
        user.level = new_level

    await session.commit()
    await session.refresh(user)

    return {
        "earned_xp": earned_xp,
        "total_xp": user.xp,
        "level": new_level,
        "leveled_up": new_level > old_level,
        "xp_to_next": xp_to_next_level(user.xp),
    }


async def update_streak(user_id: uuid.UUID, session: AsyncSession) -> dict:
    """
    스트릭(연속 학습 일수) 업데이트.

    로직:
    - 오늘 첫 대화 완료 → streak_days += 1
    - 같은 날 재대화 → 변화 없음
    - 1일 이상 공백 → streak_days = 1 (리셋)

    Redis에 `last_active:{user_id}` 키로 마지막 학습일 캐시.

    Returns:
        {"streak_days": int, "streak_updated": bool}
    """
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    today = datetime.utcnow().date()

    # Redis에서 마지막 활동일 확인 (빠른 조회)
    last_active_date = None
    try:
        redis = get_redis()
        cached = await redis.get(f"last_active:{user_id}")
        if cached:
            last_active_date = datetime.fromisoformat(cached).date()
    except Exception as e:
        logger.warning("Redis 스트릭 캐시 조회 실패: %s", e)

    # 같은 날이면 스트릭 변화 없음
    if last_active_date == today:
        return {"streak_days": user.streak_days or 0, "streak_updated": False}

    # 어제 활동했으면 연속 유지, 아니면 리셋
    if last_active_date == today - timedelta(days=1):
        user.streak_days = (user.streak_days or 0) + 1
    else:
        user.streak_days = 1  # 공백이 있었으므로 1부터 다시 시작

    await session.commit()
    await session.refresh(user)

    # Redis에 오늘 날짜 캐시 (TTL 48시간 — 2일 지나면 자동 만료)
    try:
        redis = get_redis()
        await redis.setex(
            f"last_active:{user_id}",
            172800,  # 48시간
            today.isoformat(),
        )
    except Exception as e:
        logger.warning("Redis 스트릭 캐시 저장 실패: %s", e)

    return {"streak_days": user.streak_days, "streak_updated": True}

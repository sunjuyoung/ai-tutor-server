"""
홈 화면 API — 학습 현황 대시보드 데이터

홈 화면에 표시할 종합 데이터를 단일 API로 제공:
- 유저 프로필 (XP, 레벨, 스트릭, 다음 레벨까지 잔여 XP)
- 최근 대화 목록 (최대 5개)
- 추천 시나리오 (학습 언어 기반)
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.conversation import Conversation
from app.models.persona import Persona
from app.models.scenario import Scenario
from app.models.user import User
from app.services.gamification_service import calculate_level, xp_to_next_level

router = APIRouter(prefix="/home", tags=["home"])


@router.get("")
async def get_home_data(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    홈 화면에 필요한 종합 데이터 반환.

    Returns:
        {
            "user": { xp, level, streak_days, xp_to_next, nickname, ... },
            "recent_conversations": [ { id, persona_name, persona_emoji, ... } ],
            "recommended_scenarios": [ { id, title, persona_name, ... } ]
        }
    """
    # ─── 유저 정보 ───
    level = calculate_level(current_user.xp or 0)
    xp_next = xp_to_next_level(current_user.xp or 0)

    user_data = {
        "nickname": current_user.nickname or "학습자",
        "email": current_user.email,
        "xp": current_user.xp or 0,
        "level": level,
        "streak_days": current_user.streak_days or 0,
        "xp_to_next": xp_next,
        "plan_type": current_user.plan_type,
        "target_language": current_user.target_language,
    }

    # ─── 최근 대화 (최대 5개) ───
    conv_stmt = (
        select(Conversation, Persona)
        .join(Persona, Conversation.persona_id == Persona.id)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(5)
    )
    conv_result = await session.execute(conv_stmt)
    recent_rows = conv_result.all()

    recent_conversations = []
    for conv, persona in recent_rows:
        recent_conversations.append({
            "id": str(conv.id),
            "persona_name": persona.name,
            "persona_emoji": persona.icon_emoji,
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
            "message_count": conv.message_count,
            "duration_sec": conv.duration_sec,
        })

    # ─── 추천 시나리오 (유저 학습 언어 기반, 최대 3개) ───
    scenario_stmt = (
        select(Scenario, Persona)
        .join(Persona, Scenario.persona_id == Persona.id)
        .where(Persona.language == (current_user.target_language or "en"))
        .where(Scenario.is_premium == False)  # noqa: E712 — SQLAlchemy에서 == False 필수
        .limit(3)
    )
    scenario_result = await session.execute(scenario_stmt)
    scenario_rows = scenario_result.all()

    recommended_scenarios = []
    for scenario, persona in scenario_rows:
        recommended_scenarios.append({
            "id": str(scenario.id),
            "title": scenario.title,
            "description": scenario.description,
            "icon_emoji": scenario.icon_emoji,
            "persona_name": persona.name,
            "persona_emoji": persona.icon_emoji,
            "persona_id": str(persona.id),
            "difficulty": scenario.difficulty,
            "estimated_minutes": scenario.estimated_minutes,
        })

    return {
        "user": user_data,
        "recent_conversations": recent_conversations,
        "recommended_scenarios": recommended_scenarios,
    }

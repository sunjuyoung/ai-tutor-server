"""
채팅 서비스 — 대화 생명주기 관리

담당 기능:
- 대화 생성 (AI 첫 인사 메시지 포함)
- 대화 상세 조회 (페르소나/시나리오 정보 포함)
- 메시지 저장 (유저/AI)
- 대화 히스토리 조회
- 대화 종료 + XP/스트릭 보상 처리
- 대화 삭제 (메시지 + 분석결과 포함 Hard delete)
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.conversation import Conversation
from app.models.learning_analytics import LearningAnalytics
from app.models.message import Message
from app.models.persona import Persona
from app.models.scenario import Scenario
from app.services.persona_service import build_system_prompt

logger = logging.getLogger(__name__)


async def create_conversation(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    scenario_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[Conversation, Message]:
    """Create a new conversation and generate the AI's first greeting message."""
    from app.core.openai_client import chat_stream

    # Fetch persona and scenario
    persona_result = await session.execute(select(Persona).where(Persona.id == persona_id))
    persona = persona_result.scalar_one_or_none()
    scenario_result = await session.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = scenario_result.scalar_one_or_none()

    if not persona or not scenario:
        raise ValueError("Persona or scenario not found")

    conversation = Conversation(
        user_id=user_id,
        persona_id=persona_id,
        scenario_id=scenario_id,
    )
    session.add(conversation)
    await session.flush()

    # Generate AI first message (non-streaming for the greeting)
    system_prompt = build_system_prompt(persona, scenario)
    greeting_parts = []
    async for chunk in chat_stream(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "(The learner just arrived. Greet them in character and start the conversation.)"}],
        max_tokens=150,
    ):
        greeting_parts.append(chunk)
    greeting = "".join(greeting_parts)

    # Use intro_line as fallback if API fails
    if not greeting and persona.intro_line:
        greeting = persona.intro_line

    ai_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=greeting,
    )
    session.add(ai_message)
    conversation.message_count = 1
    await session.commit()
    await session.refresh(conversation)
    await session.refresh(ai_message)
    return conversation, ai_message


async def get_conversations(user_id: uuid.UUID, session: AsyncSession, limit: int = 20, offset: int = 0) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_messages(conversation_id: uuid.UUID, session: AsyncSession) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_user_message(conversation_id: uuid.UUID, content: str, session: AsyncSession) -> Message:
    msg = Message(conversation_id=conversation_id, role="user", content=content)
    session.add(msg)

    # Update message count
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.message_count += 1
    await session.commit()
    await session.refresh(msg)
    return msg


async def save_ai_message(conversation_id: uuid.UUID, content: str, session: AsyncSession) -> Message:
    msg = Message(conversation_id=conversation_id, role="assistant", content=content)
    session.add(msg)

    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.message_count += 1
    await session.commit()
    await session.refresh(msg)
    return msg


async def end_conversation(conversation_id: uuid.UUID, session: AsyncSession) -> dict:
    """
    대화 종료 처리 + 게이미피케이션 보상 부여.

    흐름:
    1. ended_at, duration_sec 설정
    2. gamification_service.award_xp() → XP 부여 + 레벨업 확인
    3. gamification_service.update_streak() → 스트릭 업데이트
    4. 결과를 dict로 반환 (conversation + xp_result + streak_result)
    """
    from app.services.gamification_service import award_xp, update_streak

    # 1. 대화 종료 시간 및 소요 시간 설정
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()
    conv.ended_at = datetime.utcnow()
    if conv.started_at:
        conv.duration_sec = int((conv.ended_at - conv.started_at).total_seconds())
    await session.commit()
    await session.refresh(conv)

    # 2. XP 부여 (대화 시간 + 힌트 패널티 고려)
    xp_result = await award_xp(conv.user_id, conversation_id, session)
    logger.info(
        "XP awarded: conversation=%s, earned=%d, total=%d, level=%d, leveled_up=%s",
        conversation_id, xp_result["earned_xp"], xp_result["total_xp"],
        xp_result["level"], xp_result["leveled_up"],
    )

    # 3. 스트릭 업데이트
    streak_result = await update_streak(conv.user_id, session)
    logger.info(
        "Streak updated: user=%s, streak_days=%d, updated=%s",
        conv.user_id, streak_result["streak_days"], streak_result["streak_updated"],
    )

    return {
        "conversation_id": str(conv.id),
        "duration_sec": conv.duration_sec,
        "xp": xp_result,
        "streak": streak_result,
    }


async def get_conversation_context(conversation_id: uuid.UUID, session: AsyncSession) -> tuple[Persona, Scenario, list[dict]]:
    """Get persona, scenario, and message history for a conversation."""
    conv_result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_result.scalar_one()

    persona_result = await session.execute(select(Persona).where(Persona.id == conv.persona_id))
    persona = persona_result.scalar_one()

    scenario_result = await session.execute(select(Scenario).where(Scenario.id == conv.scenario_id))
    scenario = scenario_result.scalar_one()

    messages = await get_messages(conversation_id, session)
    history = [{"role": m.role, "content": m.content} for m in messages]

    return persona, scenario, history


async def get_conversation_detail(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict | None:
    """
    대화 상세 조회 — 페르소나/시나리오 메타데이터 포함.

    '대화 이어하기' 기능에서 사용. 기존 대화의 페르소나/시나리오 정보를
    프론트엔드에 전달하여 채팅 UI 헤더와 시스템 프롬프트를 복원한다.

    소유권 검증:
    - user_id가 대화의 소유자가 아니면 None 반환 (403 대신 404 처리용)
    - 존재하지 않는 대화도 None 반환

    Returns:
        dict: 대화 상세 정보 (persona/scenario 이름, 이모지 포함)
        None: 대화가 없거나 소유권 불일치
    """
    # 대화 조회
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv or conv.user_id != user_id:
        return None

    # 페르소나 정보 조회
    persona_result = await session.execute(
        select(Persona).where(Persona.id == conv.persona_id)
    )
    persona = persona_result.scalar_one_or_none()

    # 시나리오 정보 조회
    scenario_result = await session.execute(
        select(Scenario).where(Scenario.id == conv.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()

    return {
        "id": str(conv.id),
        "user_id": str(conv.user_id),
        "persona_id": str(conv.persona_id),
        "scenario_id": str(conv.scenario_id),
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
        "message_count": conv.message_count,
        "duration_sec": conv.duration_sec,
        # 프론트엔드 채팅 헤더에 표시할 페르소나/시나리오 정보
        "persona_name": persona.name if persona else "Unknown",
        "persona_emoji": persona.icon_emoji if persona else "🤖",
        "scenario_title": scenario.title if scenario else "대화",
        "scenario_emoji": scenario.icon_emoji if scenario else "💬",
    }


async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> bool:
    """
    대화 삭제 — 메시지 + 분석결과 + 대화 모두 Hard delete.

    삭제 순서 (FK 의존성 고려):
    1. learning_analytics (conversation_id FK)
    2. messages (conversation_id FK)
    3. conversation 본체

    Redis 캐시(report:{id})도 함께 정리한다.

    Args:
        conversation_id: 삭제할 대화 ID
        user_id: 요청자 ID (소유권 검증용)
        session: DB 세션

    Returns:
        True: 삭제 성공
        False: 대화가 없거나 소유권 불일치
    """
    # 소유권 검증
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv or conv.user_id != user_id:
        return False

    # 1. 분석 결과 삭제 (learning_analytics → conversation FK)
    await session.execute(
        sa_delete(LearningAnalytics).where(
            LearningAnalytics.conversation_id == conversation_id
        )
    )

    # 2. 메시지 삭제 (messages → conversation FK)
    await session.execute(
        sa_delete(Message).where(Message.conversation_id == conversation_id)
    )

    # 3. 대화 본체 삭제
    await session.delete(conv)
    await session.commit()

    # 4. Redis 리포트 캐시 정리 (캐시가 없으면 무시)
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        await redis.delete(f"report:{conversation_id}")
    except Exception:
        # Redis 연결 실패 시에도 삭제 자체는 성공 처리
        logger.warning("Failed to clear Redis cache for conversation %s", conversation_id)

    logger.info("Conversation deleted: %s (user: %s)", conversation_id, user_id)
    return True

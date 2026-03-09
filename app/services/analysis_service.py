"""
CrewAI 교정 분석 트리거 및 관리 서비스.

대화 종료 후 비동기로 CrewAI 분석을 실행하고,
결과를 DB + Redis에 저장한다.

Phase 3.5 개선:
- 대화의 언어/시나리오/난이도 메타데이터를 CrewAI에 전달
- 메시지 포맷에 턴 번호 추가 (분석 정확도 향상)
"""

import json
import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import async_session_factory
from app.core.redis import get_redis
from app.crew.correction_crew import run_correction_analysis
from app.models.conversation import Conversation
from app.models.learning_analytics import LearningAnalytics
from app.models.message import Message
from app.models.persona import Persona
from app.models.scenario import Scenario

logger = logging.getLogger(__name__)

REPORT_CACHE_TTL = 86400  # 24 hours


def _format_conversation_text(messages: list[Message]) -> str:
    """
    메시지를 CrewAI 분석용 텍스트로 포맷.

    턴 번호를 붙여서 에이전트가 특정 발화를 참조하기 쉽게 한다.
    예: [User #1] I want to order a coffee.
        [AI #2] Sure! What kind of coffee would you like?
    """
    lines = []
    user_turn = 0
    ai_turn = 0
    for msg in messages:
        if msg.role == "user":
            user_turn += 1
            lines.append(f"[User #{user_turn}] {msg.content}")
        else:
            ai_turn += 1
            lines.append(f"[AI #{ai_turn}] {msg.content}")
    return "\n".join(lines)


async def trigger_analysis(conversation_id: uuid.UUID, user_id: uuid.UUID) -> LearningAnalytics:
    """
    Trigger CrewAI correction analysis as a background task.

    This runs in a BackgroundTask context — creates its own DB session.
    """
    async with async_session_factory() as session:
        # 1. Create learning_analytics record (status=processing)
        analytics = LearningAnalytics(
            conversation_id=conversation_id,
            user_id=user_id,
            status="processing",
        )
        session.add(analytics)
        await session.commit()
        await session.refresh(analytics)
        analytics_id = analytics.id

    # Run analysis in a separate session context
    try:
        async with async_session_factory() as session:
            # 2. Fetch messages for this conversation
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            if not messages:
                logger.warning("No messages found for conversation %s", conversation_id)
                await _update_analytics_status(analytics_id, "failed")
                return analytics

            # 3. Format conversation text
            conversation_text = _format_conversation_text(messages)

            # 4. 대화의 언어/시나리오/난이도 메타데이터 로드
            conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
            conv_result = await session.execute(conv_stmt)
            conv = conv_result.scalar_one_or_none()

            language = "en"
            scenario_title = ""
            scenario_goal = ""
            difficulty = 1

            if conv:
                # 페르소나에서 언어 정보 가져오기
                persona_result = await session.execute(
                    select(Persona).where(Persona.id == conv.persona_id)
                )
                persona = persona_result.scalar_one_or_none()
                if persona:
                    language = persona.language

                # 시나리오에서 제목/목표/난이도 가져오기
                scenario_result = await session.execute(
                    select(Scenario).where(Scenario.id == conv.scenario_id)
                )
                scenario = scenario_result.scalar_one_or_none()
                if scenario:
                    scenario_title = scenario.title or ""
                    scenario_goal = scenario.goal or ""
                    difficulty = scenario.difficulty

            # 5. Run CrewAI analysis (runs in thread pool internally)
            logger.info(
                "Starting CrewAI analysis for conversation %s (language=%s, scenario=%s, difficulty=%d)",
                conversation_id, language, scenario_title, difficulty,
            )
            report = await run_correction_analysis(
                conversation_text,
                language=language,
                scenario_title=scenario_title,
                scenario_goal=scenario_goal,
                difficulty=difficulty,
            )
            logger.info("CrewAI analysis completed for conversation %s", conversation_id)

            # 5. Update analytics record with results
            stmt = select(LearningAnalytics).where(LearningAnalytics.id == analytics_id)
            result = await session.execute(stmt)
            analytics = result.scalar_one()

            analytics.corrections = [c.model_dump() if hasattr(c, "model_dump") else c for c in report.corrections]
            analytics.new_expressions = [e.model_dump() if hasattr(e, "model_dump") else e for e in report.new_expressions]
            analytics.fluency_score = report.fluency_score
            analytics.summary = report.summary
            analytics.status = "completed"
            analytics.completed_at = datetime.utcnow()

            await session.commit()
            await session.refresh(analytics)

            # 6. Cache in Redis (TTL 24h)
            try:
                redis = get_redis()
                cache_data = {
                    "id": str(analytics.id),
                    "conversation_id": str(analytics.conversation_id),
                    "corrections": analytics.corrections,
                    "new_expressions": analytics.new_expressions,
                    "fluency_score": analytics.fluency_score,
                    "summary": analytics.summary,
                    "status": analytics.status,
                    "created_at": analytics.created_at.isoformat(),
                    "completed_at": analytics.completed_at.isoformat() if analytics.completed_at else None,
                }
                await redis.setex(
                    f"report:{conversation_id}",
                    REPORT_CACHE_TTL,
                    json.dumps(cache_data),
                )
            except Exception as e:
                logger.warning("Failed to cache report in Redis: %s", e)

            return analytics

    except Exception as e:
        logger.error("CrewAI analysis failed for conversation %s: %s", conversation_id, e)
        await _update_analytics_status(analytics_id, "failed")
        raise


async def _update_analytics_status(analytics_id: uuid.UUID, status: str) -> None:
    """Update analytics status in a fresh session."""
    async with async_session_factory() as session:
        stmt = select(LearningAnalytics).where(LearningAnalytics.id == analytics_id)
        result = await session.execute(stmt)
        analytics = result.scalar_one_or_none()
        if analytics:
            analytics.status = status
            await session.commit()


async def get_report(conversation_id: uuid.UUID, session: AsyncSession) -> LearningAnalytics | None:
    """Get the analysis report for a conversation. Checks Redis cache first."""
    # Try Redis cache first
    try:
        redis = get_redis()
        cached = await redis.get(f"report:{conversation_id}")
        if cached:
            data = json.loads(cached)
            if data.get("status") == "completed":
                # Reconstruct from cache
                return LearningAnalytics(
                    id=uuid.UUID(data["id"]),
                    conversation_id=uuid.UUID(data["conversation_id"]),
                    corrections=data.get("corrections"),
                    new_expressions=data.get("new_expressions"),
                    fluency_score=data.get("fluency_score"),
                    summary=data.get("summary"),
                    status=data["status"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
                )
    except Exception as e:
        logger.warning("Redis cache read failed: %s", e)

    # Fallback to DB
    stmt = (
        select(LearningAnalytics)
        .where(LearningAnalytics.conversation_id == conversation_id)
        .order_by(LearningAnalytics.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

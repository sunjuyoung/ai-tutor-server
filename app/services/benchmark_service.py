"""
벤치마크 서비스 — Before/After 성장 측정

Phase 3 (W14) 핵심 기능:
1. 벤치마크 대화 종료 시 자동 측정 (문법 오류, 새 표현, 힌트, 유창성)
2. 동일 시나리오 라운드별 점수 비교
3. 14일 경과 시나리오 재도전 알림 조회
4. 페르소나 코멘트 생성
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.conversation import Conversation
from app.models.learning_analytics import LearningAnalytics
from app.models.persona import Persona
from app.models.scenario import Scenario
from app.models.scenario_benchmark import ScenarioBenchmark

logger = logging.getLogger(__name__)


async def create_benchmark(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> ScenarioBenchmark | None:
    """
    벤치마크 대화 종료 시 호출 — 분석 결과를 기반으로 벤치마크 레코드 생성.

    learning_analytics가 완료되어 있어야 정확한 측정이 가능하다.
    아직 미완료라면 기본값으로 생성하고, 나중에 업데이트한다.
    """
    # 대화 정보 조회
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        return None

    # 기존 라운드 수 확인 (현재 유저×시나리오)
    round_stmt = (
        select(ScenarioBenchmark)
        .where(ScenarioBenchmark.user_id == user_id)
        .where(ScenarioBenchmark.scenario_id == conv.scenario_id)
        .order_by(ScenarioBenchmark.round_number.desc())
    )
    round_result = await session.execute(round_stmt)
    last_round = round_result.first()
    next_round = (last_round[0].round_number + 1) if last_round else 1

    # 분석 결과 조회 (있으면 사용)
    analytics_result = await session.execute(
        select(LearningAnalytics)
        .where(LearningAnalytics.conversation_id == conversation_id)
        .where(LearningAnalytics.status == "completed")
    )
    analytics = analytics_result.scalar_one_or_none()

    grammar_errors = 0
    new_expressions_count = 0
    fluency = None

    if analytics:
        grammar_errors = len(analytics.corrections or [])
        new_expressions_count = len(analytics.new_expressions or [])
        fluency = analytics.fluency_score

    # 페르소나 코멘트 생성
    persona_comment = await _generate_persona_comment(
        conv.persona_id, conv.scenario_id, next_round, fluency, session
    )

    benchmark = ScenarioBenchmark(
        user_id=user_id,
        scenario_id=conv.scenario_id,
        conversation_id=conversation_id,
        round_number=next_round,
        grammar_errors=grammar_errors,
        new_expressions=new_expressions_count,
        hint_count=conv.hint_count,
        fluency_score=fluency,
        persona_comment=persona_comment,
    )
    session.add(benchmark)
    await session.commit()
    await session.refresh(benchmark)

    logger.info(
        "벤치마크 생성: scenario=%s, round=%d, fluency=%s",
        conv.scenario_id, next_round, fluency,
    )
    return benchmark


async def get_comparison(
    user_id: uuid.UUID,
    scenario_id: uuid.UUID,
    session: AsyncSession,
) -> dict | None:
    """
    유저×시나리오 Before/After 비교 데이터 반환.

    Returns:
        {
            scenario_id, scenario_title, scenario_emoji, persona_name,
            rounds: [...],
            improvement: { grammar_change, expression_change, ... }
        }
    """
    # 시나리오/페르소나 정보
    scenario_result = await session.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()
    if not scenario:
        return None

    persona_result = await session.execute(
        select(Persona).where(Persona.id == scenario.persona_id)
    )
    persona = persona_result.scalar_one_or_none()

    # 라운드별 벤치마크
    stmt = (
        select(ScenarioBenchmark)
        .where(ScenarioBenchmark.user_id == user_id)
        .where(ScenarioBenchmark.scenario_id == scenario_id)
        .order_by(ScenarioBenchmark.round_number)
    )
    result = await session.execute(stmt)
    benchmarks = list(result.scalars().all())

    if not benchmarks:
        return None

    rounds = [
        {
            "id": str(b.id),
            "scenario_id": str(b.scenario_id),
            "conversation_id": str(b.conversation_id),
            "round_number": b.round_number,
            "grammar_errors": b.grammar_errors,
            "new_expressions": b.new_expressions,
            "hint_count": b.hint_count,
            "fluency_score": b.fluency_score,
            "response_time_avg": b.response_time_avg,
            "persona_comment": b.persona_comment,
            "created_at": b.created_at.isoformat(),
        }
        for b in benchmarks
    ]

    # 성장 요약 계산 (첫 라운드 vs 최신 라운드)
    improvement = None
    if len(benchmarks) >= 2:
        first = benchmarks[0]
        latest = benchmarks[-1]
        improvement = {
            "grammar_errors": {
                "before": first.grammar_errors,
                "after": latest.grammar_errors,
                "change_pct": _calc_change_pct(first.grammar_errors, latest.grammar_errors),
            },
            "new_expressions": {
                "before": first.new_expressions,
                "after": latest.new_expressions,
                "change": latest.new_expressions - first.new_expressions,
            },
            "hint_count": {
                "before": first.hint_count,
                "after": latest.hint_count,
                "change_pct": _calc_change_pct(first.hint_count, latest.hint_count),
            },
            "fluency_score": {
                "before": first.fluency_score,
                "after": latest.fluency_score,
                "change": (latest.fluency_score or 0) - (first.fluency_score or 0),
            },
        }

    return {
        "scenario_id": str(scenario.id),
        "scenario_title": scenario.title,
        "scenario_emoji": scenario.icon_emoji,
        "persona_name": persona.name if persona else "Unknown",
        "rounds": rounds,
        "improvement": improvement,
    }


async def get_benchmark_reminders(
    user_id: uuid.UUID,
    session: AsyncSession,
    days_threshold: int = 14,
) -> list[dict]:
    """
    14일 이상 경과한 시나리오 벤치마크 → 재도전 알림 목록.
    홈 화면에서 사용.
    """
    cutoff = datetime.utcnow() - timedelta(days=days_threshold)

    # 유저의 모든 벤치마크에서 시나리오별 가장 최근 라운드 조회
    stmt = (
        select(ScenarioBenchmark)
        .where(ScenarioBenchmark.user_id == user_id)
        .order_by(
            ScenarioBenchmark.scenario_id,
            ScenarioBenchmark.round_number.desc(),
        )
    )
    result = await session.execute(stmt)
    all_benchmarks = list(result.scalars().all())

    # 시나리오별 가장 최근 벤치마크만 추출
    seen_scenarios: set[uuid.UUID] = set()
    latest_per_scenario: list[ScenarioBenchmark] = []
    for b in all_benchmarks:
        if b.scenario_id not in seen_scenarios:
            seen_scenarios.add(b.scenario_id)
            latest_per_scenario.append(b)

    reminders = []
    for b in latest_per_scenario:
        # 14일 이상 경과한 것만
        if b.created_at > cutoff:
            continue

        # 시나리오/페르소나 정보 조회
        scenario_result = await session.execute(
            select(Scenario).where(Scenario.id == b.scenario_id)
        )
        scenario = scenario_result.scalar_one_or_none()
        if not scenario:
            continue

        persona_result = await session.execute(
            select(Persona).where(Persona.id == scenario.persona_id)
        )
        persona = persona_result.scalar_one_or_none()

        days_since = (datetime.utcnow() - b.created_at).days

        reminders.append({
            "scenario_id": str(b.scenario_id),
            "scenario_title": scenario.title,
            "scenario_emoji": scenario.icon_emoji,
            "persona_name": persona.name if persona else "Unknown",
            "days_since_last": days_since,
            "last_fluency_score": b.fluency_score,
        })

    return reminders


async def _generate_persona_comment(
    persona_id: uuid.UUID,
    scenario_id: uuid.UUID,
    round_number: int,
    fluency_score: int | None,
    session: AsyncSession,
) -> str | None:
    """벤치마크 결과에 대한 페르소나 코멘트 생성 (LLM)"""
    persona_result = await session.execute(
        select(Persona).where(Persona.id == persona_id)
    )
    persona = persona_result.scalar_one_or_none()
    if not persona:
        return None

    try:
        from app.core.openai_client import get_openai_client

        client = get_openai_client()
        prompt = (
            f"You are {persona.name} ({persona.personality}). "
            f"The learner just completed round {round_number} of a scenario. "
            f"Their fluency score is {fluency_score or 'unknown'}/100. "
            f"Write a short encouraging comment (1-2 sentences) in {persona.language}. "
            f"Match your speech style: {persona.speech_style}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=100,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("페르소나 코멘트 생성 실패: %s", e)
        return None


def _calc_change_pct(before: int, after: int) -> float | None:
    """변화율 계산 (감소는 음수)"""
    if before == 0:
        return None
    return round(((after - before) / before) * 100, 1)

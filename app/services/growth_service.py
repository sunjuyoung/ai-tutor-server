"""
성장 대시보드 서비스 — 주간/월간 학습 통계 집계

Phase 3 (W14) 성장 대시보드:
- 주간 요약 (총 대화 시간, 평균 응답 속도, 배운 표현, 오류 추이)
- 문법 오류 추이 라인 차트 데이터
- 시나리오별 최고 유창성 점수
- 자주 틀리는 패턴 Top N
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.conversation import Conversation
from app.models.learning_analytics import LearningAnalytics
from app.models.scenario import Scenario

logger = logging.getLogger(__name__)


async def get_growth_dashboard(
    user_id: uuid.UUID,
    period: str,  # "weekly" | "monthly"
    session: AsyncSession,
) -> dict:
    """
    성장 대시보드 종합 데이터 반환.

    Returns:
        {
            summary: { total_duration_min, avg_fluency, total_expressions, total_errors },
            error_trend: [ { week, error_count } ],
            scenario_scores: [ { scenario_id, title, emoji, best_fluency } ],
            common_errors: [ { pattern, count } ],
        }
    """
    # 기간 설정
    if period == "monthly":
        since = datetime.utcnow() - timedelta(days=30)
    else:
        since = datetime.utcnow() - timedelta(days=7)

    # ─── 1. 기간 내 완료된 대화 조회 ───
    conv_stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .where(Conversation.ended_at.isnot(None))
        .where(Conversation.started_at >= since)
        .order_by(Conversation.started_at)
    )
    conv_result = await session.execute(conv_stmt)
    conversations = list(conv_result.scalars().all())

    # 총 대화 시간 (분)
    total_duration_sec = sum(c.duration_sec or 0 for c in conversations)
    total_duration_min = round(total_duration_sec / 60, 1)

    # ─── 2. 분석 결과 조회 ───
    conv_ids = [c.id for c in conversations]
    analytics_list = []
    if conv_ids:
        analytics_stmt = (
            select(LearningAnalytics)
            .where(LearningAnalytics.user_id == user_id)
            .where(LearningAnalytics.conversation_id.in_(conv_ids))
            .where(LearningAnalytics.status == "completed")
        )
        analytics_result = await session.execute(analytics_stmt)
        analytics_list = list(analytics_result.scalars().all())

    # 평균 유창성
    fluency_scores = [a.fluency_score for a in analytics_list if a.fluency_score is not None]
    avg_fluency = round(sum(fluency_scores) / len(fluency_scores)) if fluency_scores else None

    # 총 배운 표현 수
    total_expressions = sum(len(a.new_expressions or []) for a in analytics_list)

    # 총 오류 수
    total_errors = sum(len(a.corrections or []) for a in analytics_list)

    # ─── 3. 주간 오류 추이 (최근 6주) ───
    error_trend = await _get_error_trend(user_id, session)

    # ─── 4. 시나리오별 최고 점수 ───
    scenario_scores = await _get_scenario_scores(user_id, session)

    # ─── 5. 자주 틀리는 패턴 Top 3 ───
    common_errors = _extract_common_errors(analytics_list, top_n=3)

    return {
        "summary": {
            "total_duration_min": total_duration_min,
            "total_conversations": len(conversations),
            "avg_fluency": avg_fluency,
            "total_expressions": total_expressions,
            "total_errors": total_errors,
        },
        "error_trend": error_trend,
        "scenario_scores": scenario_scores,
        "common_errors": common_errors,
    }


async def _get_error_trend(
    user_id: uuid.UUID,
    session: AsyncSession,
    weeks: int = 6,
) -> list[dict]:
    """최근 N주간 주별 문법 오류 수 추이"""
    trend = []
    now = datetime.utcnow()

    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)

        # 해당 주간 대화 ID 조회
        conv_stmt = (
            select(Conversation.id)
            .where(Conversation.user_id == user_id)
            .where(Conversation.ended_at.isnot(None))
            .where(Conversation.started_at >= week_start)
            .where(Conversation.started_at < week_end)
        )
        conv_result = await session.execute(conv_stmt)
        conv_ids = [row[0] for row in conv_result.all()]

        error_count = 0
        if conv_ids:
            analytics_stmt = (
                select(LearningAnalytics)
                .where(LearningAnalytics.conversation_id.in_(conv_ids))
                .where(LearningAnalytics.status == "completed")
            )
            analytics_result = await session.execute(analytics_stmt)
            for a in analytics_result.scalars().all():
                error_count += len(a.corrections or [])

        trend.append({
            "week_label": f"W{weeks - i}",
            "week_start": week_start.strftime("%m/%d"),
            "error_count": error_count,
        })

    return trend


async def _get_scenario_scores(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[dict]:
    """시나리오별 최고 유창성 점수"""
    # 유저의 완료된 대화를 시나리오별로 그룹핑
    stmt = (
        select(
            Conversation.scenario_id,
            func.max(LearningAnalytics.fluency_score).label("best_fluency"),
        )
        .join(LearningAnalytics, LearningAnalytics.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .where(LearningAnalytics.status == "completed")
        .group_by(Conversation.scenario_id)
    )
    result = await session.execute(stmt)
    rows = result.all()

    scores = []
    for row in rows:
        scenario_result = await session.execute(
            select(Scenario).where(Scenario.id == row.scenario_id)
        )
        scenario = scenario_result.scalar_one_or_none()
        if scenario:
            scores.append({
                "scenario_id": str(scenario.id),
                "title": scenario.title,
                "emoji": scenario.icon_emoji,
                "best_fluency": row.best_fluency,
            })

    return scores


def _extract_common_errors(
    analytics_list: list[LearningAnalytics],
    top_n: int = 3,
) -> list[dict]:
    """분석 결과에서 자주 틀리는 error_type 패턴 추출"""
    error_counts: dict[str, int] = {}

    for a in analytics_list:
        for correction in (a.corrections or []):
            error_type = correction.get("error_type", "unknown")
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

    # 빈도 내림차순 정렬
    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

    return [
        {"pattern": pattern, "count": count}
        for pattern, count in sorted_errors[:top_n]
    ]

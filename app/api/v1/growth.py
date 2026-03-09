"""
성장 대시보드 API — 학습 통계 + 오류 추이

Phase 3 (W14):
- GET /growth: 주간/월간 성장 대시보드 데이터
  - summary: 총 대화 시간, 평균 유창성, 배운 표현 수, 오류 수
  - error_trend: 주별 오류 추이 (라인 차트용)
  - scenario_scores: 시나리오별 최고 유창성 점수
  - common_errors: 자주 틀리는 패턴 Top 3
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.services import growth_service

router = APIRouter(prefix="/growth", tags=["growth"])


@router.get("")
async def get_growth_data(
    period: str = Query("weekly", pattern="^(weekly|monthly)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    성장 대시보드 종합 데이터.

    Query Params:
        period: "weekly" (기본) | "monthly"

    Returns:
        summary, error_trend, scenario_scores, common_errors
    """
    return await growth_service.get_growth_dashboard(
        current_user.id, period, session
    )

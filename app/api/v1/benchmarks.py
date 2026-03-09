"""
벤치마크 API — Before/After 성장 측정 엔드포인트

Phase 3 (W14):
- GET /benchmarks/{scenario_id}: 시나리오별 라운드 비교 데이터
- GET /benchmarks/reminders: 14일 경과 재도전 알림 목록
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.services import benchmark_service

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("/reminders")
async def get_reminders(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    재도전 알림 목록 — 14일 이상 경과한 벤치마크 시나리오.

    홈 화면 "성장 확인" 카드에 사용.
    """
    reminders = await benchmark_service.get_benchmark_reminders(
        current_user.id, session
    )
    return reminders


@router.get("/{scenario_id}")
async def get_benchmark_comparison(
    scenario_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    시나리오별 Before/After 비교 데이터.

    Before/After 리포트 화면에서 사용.
    라운드별 점수 + 성장 요약 (improvement) 반환.
    """
    comparison = await benchmark_service.get_comparison(
        current_user.id, scenario_id, session
    )
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 시나리오의 벤치마크 기록이 없습니다.",
        )
    return comparison

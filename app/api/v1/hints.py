"""
힌트 API 엔드포인트 — 대화 중 맥락 기반 표현 추천

사용 흐름:
1. 학습자가 대화 중 막힐 때 힌트 버튼 클릭
2. POST /hints/{conversation_id} 호출
3. GPT-4o가 최근 대화 맥락을 분석하여 자연스러운 표현 추천
4. hint_count 증가 → 대화 종료 시 XP 패널티 적용
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.services.hint_service import generate_hint

router = APIRouter(prefix="/hints", tags=["hints"])


@router.post("/{conversation_id}")
async def get_hint(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    대화 맥락 기반 힌트 생성.

    Returns:
        {
            "expression": "자연스러운 표현",
            "pronunciation": "발음 가이드",
            "meaning_ko": "한국어 뜻"
        }
    """
    try:
        hint = await generate_hint(conversation_id, session)
        return hint
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"힌트 생성 실패: {str(e)}")

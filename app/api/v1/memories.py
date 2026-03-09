"""
기억 API — 페르소나 기억 시스템 엔드포인트

Phase 3 (W12~W13):
- GET /memories/{persona_id}: 유저×페르소나 기억 목록 조회
- 기억 추출/저장은 대화 종료 시 자동 실행 (chat.py → memory_service)
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.services import memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/{persona_id}")
async def get_memories(
    persona_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    유저×페르소나 기억 목록 조회.

    페르소나 상세 화면에서 "이전 대화: N회, 너를 기억하고 있어요" 표시에 사용.
    """
    memories = await memory_service.get_user_persona_memories(
        current_user.id, persona_id, session
    )
    return {
        "memories": [
            {
                "id": str(m.id),
                "persona_id": str(m.persona_id),
                "memory_type": m.memory_type,
                "content": m.content,
                "last_referenced_at": m.last_referenced_at.isoformat(),
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ],
        "total": len(memories),
    }

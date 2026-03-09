"""
TTS API — 텍스트를 음성으로 변환

Phase 3.5: ChatBubble 🔊 버튼 / 음성 모드 자동 재생에서 호출.
페르소나의 tts_voice를 사용하여 개성 있는 음성을 생성한다.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.persona import Persona
from app.models.user import User
from app.services.tts_service import synthesize

router = APIRouter(prefix="/tts", tags=["tts"])


class TTSRequest(BaseModel):
    """TTS 요청 바디"""
    text: str  # 합성할 텍스트
    persona_id: uuid.UUID  # 페르소나 음성 결정용


@router.post("")
async def text_to_speech(
    body: TTSRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    텍스트를 페르소나 음성으로 변환하여 mp3 바이트 반환.

    프론트엔드에서 AI 메시지 재생 시 호출:
    - 음성 모드 자동 재생
    - ChatBubble 🔊 버튼 클릭
    """
    if not body.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required")

    # 페르소나의 TTS 음성 조회
    result = await session.execute(select(Persona).where(Persona.id == body.persona_id))
    persona = result.scalar_one_or_none()
    voice = persona.tts_voice if persona else "nova"

    # TTS 합성
    audio_bytes = await synthesize(body.text, voice=voice)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=tts.mp3"},
    )

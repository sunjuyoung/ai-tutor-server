"""
TTS 서비스 — OpenAI TTS API 음성 합성

담당 기능:
- 텍스트를 mp3 오디오로 변환
- 페르소나별 음성 지정 (alloy/echo/fable/onyx/nova/shimmer)
"""

import logging

from app.core.openai_client import get_openai_client

logger = logging.getLogger(__name__)

# 유효한 OpenAI TTS 음성 목록
VALID_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}


async def synthesize(text: str, voice: str = "nova") -> bytes:
    """
    텍스트를 mp3 오디오 바이트로 변환 (OpenAI TTS API).

    Args:
        text: 합성할 텍스트
        voice: TTS 음성 (alloy|echo|fable|onyx|nova|shimmer)

    Returns:
        mp3 오디오 바이트
    """
    # 유효하지 않은 음성은 기본값으로 폴백
    if voice not in VALID_VOICES:
        logger.warning("유효하지 않은 TTS voice '%s', 'nova'로 폴백", voice)
        voice = "nova"

    client = get_openai_client()

    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )

    # response.content가 바이트 데이터 (mp3)
    audio_bytes = response.content
    logger.info("TTS 합성 완료: voice=%s, text_length=%d, audio_bytes=%d", voice, len(text), len(audio_bytes))
    return audio_bytes

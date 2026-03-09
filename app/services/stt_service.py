"""
STT 서비스 — OpenAI Whisper API 음성 인식

담당 기능:
- 오디오 바이트를 텍스트로 변환 (Whisper API)
- 언어 힌트 지원 (en/ja)
"""

import logging
from io import BytesIO

from app.core.openai_client import get_openai_client

logger = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """
    오디오 바이트를 텍스트로 변환 (OpenAI Whisper API).

    Args:
        audio_bytes: webm/opus 등 오디오 데이터
        language: 언어 코드 ("en" | "ja")

    Returns:
        변환된 텍스트
    """
    client = get_openai_client()

    # Whisper API는 file-like object를 받으므로 BytesIO로 감싸기
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.webm"  # 파일 확장자 힌트

    result = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language=language,
    )

    logger.info("STT 변환 완료: language=%s, text_length=%d", language, len(result.text))
    return result.text

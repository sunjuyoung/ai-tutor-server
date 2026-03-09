"""
힌트 서비스 — 대화 중 맥락 기반 표현 힌트 생성

직접 OpenAI API 사용 (CrewAI X — 실시간 응답이 필요하므로).
대화 컨텍스트를 분석하여 학습자가 사용할 만한 자연스러운 표현을 추천.

힌트를 사용하면 conversation.hint_count가 증가하고,
대화 종료 시 XP 계산에서 50%씩 패널티가 적용됨.
"""

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.openai_client import get_openai_client
from app.models.conversation import Conversation
from app.models.message import Message

logger = logging.getLogger(__name__)

# 힌트 생성 전용 시스템 프롬프트
HINT_SYSTEM_PROMPT = """You are a language learning assistant.
Based on the conversation context, suggest ONE natural expression that the learner could use next.

Return ONLY a JSON object with these fields:
- expression: the suggested expression in the target language
- pronunciation: romanized pronunciation (for Japanese) or phonetic guide
- meaning_ko: Korean translation/explanation

Keep the expression short and contextually relevant.
Example: {"expression": "That sounds amazing!", "pronunciation": "That sounds amazing!", "meaning_ko": "정말 대단하다!"}
"""


async def generate_hint(
    conversation_id: uuid.UUID,
    session: AsyncSession,
) -> dict:
    """
    대화 맥락을 분석하여 힌트(추천 표현)를 생성.

    흐름:
    1. 최근 메시지 5개 조회 (컨텍스트 최소화 → 빠른 응답)
    2. GPT-4o로 힌트 생성 (max_tokens=150, 비스트리밍)
    3. JSON 파싱하여 반환
    4. conversation.hint_count 증가 (XP 패널티용)

    Returns:
        {"expression": str, "pronunciation": str, "meaning_ko": str}

    Raises:
        ValueError: 대화를 찾을 수 없을 때
    """
    # 1. 대화 + 최근 메시지 조회
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    # 최근 5개 메시지만 가져옴 (컨텍스트 최적화)
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(5)
    )
    msg_result = await session.execute(msg_stmt)
    recent_messages = list(reversed(list(msg_result.scalars().all())))

    # 2. OpenAI에 힌트 요청 (비스트리밍 — 빠른 단일 응답)
    client = get_openai_client()
    messages = [
        {"role": "system", "content": HINT_SYSTEM_PROMPT},
    ]
    # 대화 컨텍스트 추가
    for msg in recent_messages:
        messages.append({
            "role": msg.role,
            "content": msg.content,
        })
    # 힌트 요청 메시지
    messages.append({
        "role": "user",
        "content": "Based on this conversation, suggest a natural expression I could use next. Return JSON only.",
    })

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=150,
        temperature=0.7,
    )

    raw_content = response.choices[0].message.content or ""

    # 3. JSON 파싱 (마크다운 코드블록 대응)
    hint = _parse_hint_json(raw_content)

    # 4. hint_count 증가
    conv.hint_count += 1
    await session.commit()

    return hint


def _parse_hint_json(raw: str) -> dict:
    """
    GPT 응답에서 힌트 JSON을 안전하게 추출.

    마크다운 코드블록(```json ... ```)이 포함된 경우도 처리.

    Returns:
        파싱된 dict. 실패 시 기본값 반환.
    """
    default = {
        "expression": "Let me think about that...",
        "pronunciation": "Let me think about that...",
        "meaning_ko": "그것에 대해 생각해 볼게요...",
    }

    if not raw:
        return default

    # 직접 파싱 시도
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # 마크다운 코드블록에서 추출
    for marker in ["```json", "```"]:
        if marker in raw:
            parts = raw.split(marker)
            if len(parts) > 1:
                json_str = parts[1].split("```")[0].strip()
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, TypeError):
                    pass

    # JSON 객체 패턴 탐색 ({ ... })
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    logger.warning("힌트 JSON 파싱 실패: %s", raw[:200])
    return default

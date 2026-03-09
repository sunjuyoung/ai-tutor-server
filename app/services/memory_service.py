"""
기억 서비스 — 페르소나 기억 추출/저장/검색

Phase 3 (W12~W13) 핵심 기능:
1. 대화 종료 시 LLM으로 핵심 정보 추출
2. text-embedding-3-small로 임베딩 생성
3. pgvector 코사인 유사도 검색으로 중복 체크 (>0.85 → 업데이트)
4. 대화 시작 시 관련 기억 Top 5 조회
5. 상한 50건/유저×페르소나, 90일 미참조 아카이브
"""

import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.openai_client import get_openai_client
from app.models.message import Message
from app.models.persona_memory import PersonaMemory

logger = logging.getLogger(__name__)

# ─── 기억 추출 프롬프트 ───
EXTRACT_PROMPT = """
다음 대화에서 기억할 만한 유저의 개인정보, 관심사, 상황을 추출하세요.
전화번호, 주소, 비밀번호 등 민감 정보는 절대 추출하지 마세요.

JSON 배열로만 응답하세요 (다른 텍스트 없이):
[
  {"type": "preference", "content": "고양이 2마리를 키움 (이름: 모찌, 콩)"},
  {"type": "milestone", "content": "다음 주 화요일에 취업 면접 예정"}
]

type은 다음 중 하나:
- preference: 취향, 관심사, 좋아하는 것
- milestone: 예정 이벤트, 중요한 일정
- personal_info: 직업, 나이, 거주지 등 기본 정보

기억할 만한 내용이 없으면 빈 배열 []을 반환하세요.
"""

# 유사도 임계값: 이 이상이면 동일한 기억으로 판단
SIMILARITY_THRESHOLD = 0.85
# 유저×페르소나당 최대 기억 수
MAX_MEMORIES_PER_PAIR = 50
# 미참조 아카이브 기준 일수
ARCHIVE_DAYS = 90


async def _create_embedding(text_content: str) -> list[float]:
    """OpenAI text-embedding-3-small로 임베딩 벡터 생성"""
    client = get_openai_client()
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text_content,
    )
    return response.data[0].embedding


async def extract_and_save(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    session: AsyncSession,
) -> list[dict]:
    """
    대화 종료 시 호출 — 기억 추출 → 임베딩 → 중복검사 → 저장

    Returns:
        추출/저장된 기억 목록
    """
    # 1. 대화 히스토리 로드
    msg_result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = list(msg_result.scalars().all())

    if len(messages) < 2:
        # 메시지가 너무 적으면 기억 추출 스킵
        return []

    # 대화 텍스트 구성
    conversation_text = "\n".join(
        f"{'User' if m.role == 'user' else 'AI'}: {m.content}"
        for m in messages
    )

    # 2. LLM으로 기억 추출
    client = get_openai_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # 비용 절약을 위해 mini 사용
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        raw = response.choices[0].message.content or "[]"
        memories = _parse_json_safe(raw)
    except Exception as e:
        logger.error("기억 추출 LLM 호출 실패: %s", e)
        return []

    saved = []
    for mem in memories:
        mem_type = mem.get("type", "preference")
        content = mem.get("content", "").strip()
        if not content:
            continue

        try:
            # 3. 임베딩 생성
            embedding = await _create_embedding(content)

            # 4. 중복 검사 (pgvector 코사인 유사도)
            similar = await find_similar(
                user_id, persona_id, embedding, session
            )

            if similar:
                # 기존 기억 업데이트
                similar.content = content
                similar.embedding = embedding
                similar.updated_at = datetime.utcnow()
                similar.last_referenced_at = datetime.utcnow()
                similar.source_conversation_id = conversation_id
                await session.commit()
                logger.info("기억 업데이트: %s", content[:50])
            else:
                # 새 기억 생성 (상한 체크 후)
                await _enforce_memory_limit(user_id, persona_id, session)
                new_memory = PersonaMemory(
                    user_id=user_id,
                    persona_id=persona_id,
                    memory_type=mem_type,
                    content=content,
                    embedding=embedding,
                    source_conversation_id=conversation_id,
                )
                session.add(new_memory)
                await session.commit()
                logger.info("새 기억 저장: %s", content[:50])

            saved.append(mem)
        except Exception as e:
            logger.error("기억 저장 실패 (%s): %s", content[:30], e)
            continue

    return saved


async def find_similar(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    embedding: list[float],
    session: AsyncSession,
) -> PersonaMemory | None:
    """
    pgvector 코사인 유사도로 중복 기억 검색.
    SIMILARITY_THRESHOLD(0.85) 이상이면 가장 유사한 기억 반환.
    """
    # 코사인 거리: 1 - cosine_similarity, 따라서 거리가 작을수록 유사
    # threshold 0.85 → 거리 0.15 이하
    distance_threshold = 1 - SIMILARITY_THRESHOLD
    embedding_str = str(embedding)

    stmt = text("""
        SELECT id, content, memory_type, embedding <=> :embedding AS distance
        FROM persona_memories
        WHERE user_id = :user_id
          AND persona_id = :persona_id
          AND embedding <=> :embedding < :threshold
        ORDER BY distance
        LIMIT 1
    """)

    result = await session.execute(
        stmt,
        {
            "user_id": str(user_id),
            "persona_id": str(persona_id),
            "embedding": embedding_str,
            "threshold": distance_threshold,
        },
    )
    row = result.first()
    if not row:
        return None

    # 해당 ID로 ORM 객체 로드
    mem_result = await session.execute(
        select(PersonaMemory).where(PersonaMemory.id == row.id)
    )
    return mem_result.scalar_one_or_none()


async def get_relevant_memories(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    context_text: str,
    session: AsyncSession,
    top_k: int = 5,
) -> list[PersonaMemory]:
    """
    대화 시작 시 호출 — 시나리오 맥락으로 관련 기억 Top K 조회.
    조회된 기억의 last_referenced_at을 갱신한다.
    """
    try:
        embedding = await _create_embedding(context_text)
    except Exception as e:
        logger.error("기억 검색용 임베딩 생성 실패: %s", e)
        return []

    embedding_str = str(embedding)

    stmt = text("""
        SELECT id, embedding <=> :embedding AS distance
        FROM persona_memories
        WHERE user_id = :user_id
          AND persona_id = :persona_id
        ORDER BY distance
        LIMIT :top_k
    """)

    result = await session.execute(
        stmt,
        {
            "user_id": str(user_id),
            "persona_id": str(persona_id),
            "embedding": embedding_str,
            "top_k": top_k,
        },
    )
    rows = result.all()

    memories = []
    for row in rows:
        mem_result = await session.execute(
            select(PersonaMemory).where(PersonaMemory.id == row.id)
        )
        mem = mem_result.scalar_one_or_none()
        if mem:
            # 참조 시각 갱신
            mem.last_referenced_at = datetime.utcnow()
            memories.append(mem)

    if memories:
        await session.commit()

    return memories


async def get_user_persona_memories(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    session: AsyncSession,
) -> list[PersonaMemory]:
    """유저×페르소나의 모든 기억 목록 조회"""
    stmt = (
        select(PersonaMemory)
        .where(PersonaMemory.user_id == user_id)
        .where(PersonaMemory.persona_id == persona_id)
        .order_by(PersonaMemory.last_referenced_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _enforce_memory_limit(
    user_id: uuid.UUID,
    persona_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """
    기억 상한(50건) 초과 시 가장 오래된 기억 삭제.
    90일 미참조 기억을 우선 삭제한다.
    """
    # 현재 기억 수 확인
    count_stmt = (
        select(func.count(PersonaMemory.id))
        .where(PersonaMemory.user_id == user_id)
        .where(PersonaMemory.persona_id == persona_id)
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    if total < MAX_MEMORIES_PER_PAIR:
        return

    # 90일 미참조 기억 우선 삭제
    archive_cutoff = datetime.utcnow() - timedelta(days=ARCHIVE_DAYS)
    old_stmt = (
        select(PersonaMemory)
        .where(PersonaMemory.user_id == user_id)
        .where(PersonaMemory.persona_id == persona_id)
        .where(PersonaMemory.last_referenced_at < archive_cutoff)
        .order_by(PersonaMemory.last_referenced_at)
        .limit(1)
    )
    old_result = await session.execute(old_stmt)
    old_mem = old_result.scalar_one_or_none()

    if old_mem:
        await session.delete(old_mem)
        await session.commit()
        return

    # 90일 미참조가 없으면 가장 오래된 기억 삭제
    oldest_stmt = (
        select(PersonaMemory)
        .where(PersonaMemory.user_id == user_id)
        .where(PersonaMemory.persona_id == persona_id)
        .order_by(PersonaMemory.last_referenced_at)
        .limit(1)
    )
    oldest_result = await session.execute(oldest_stmt)
    oldest = oldest_result.scalar_one_or_none()
    if oldest:
        await session.delete(oldest)
        await session.commit()


def _parse_json_safe(raw: str) -> list[dict]:
    """LLM 응답에서 JSON 배열 안전하게 추출"""
    try:
        # 마크다운 코드블록 제거
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("기억 추출 JSON 파싱 실패: %s", raw[:100])
        return []

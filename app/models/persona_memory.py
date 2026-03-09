"""
페르소나 기억 모델 — 유저×페르소나 별 기억 저장

Phase 3 (W12~W13) 페르소나 기억 시스템:
- 대화 종료 시 LLM이 추출한 유저 정보/관심사를 저장
- pgvector 임베딩으로 유사도 검색 (중복 방지 + 관련 기억 조회)
- 기억 타입: preference(선호), milestone(이벤트), personal_info(개인정보)
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class PersonaMemory(SQLModel, table=True):
    __tablename__ = "persona_memories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    persona_id: uuid.UUID = Field(foreign_key="personas.id", index=True)

    # 기억 타입: preference | milestone | personal_info
    memory_type: str = Field(max_length=30)
    # 기억 내용 (자연어 텍스트)
    content: str = Field(max_length=500)
    # text-embedding-3-small 벡터 (1536차원)
    embedding: list[float] = Field(sa_column=Column(Vector(1536)))

    # 출처 대화 ID (어떤 대화에서 추출했는지)
    source_conversation_id: uuid.UUID | None = Field(
        default=None, foreign_key="conversations.id"
    )

    # 마지막 참조 시각 (90일 미참조 시 아카이브 대상)
    last_referenced_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

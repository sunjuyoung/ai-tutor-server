"""
기억 시스템 스키마 — 요청/응답 모델

Phase 3 (W12~W13): 페르소나 기억 시스템
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class MemoryRead(BaseModel):
    """기억 조회 응답"""
    id: uuid.UUID
    persona_id: uuid.UUID
    memory_type: str
    content: str
    last_referenced_at: datetime
    created_at: datetime


class MemoryListResponse(BaseModel):
    """유저×페르소나 기억 목록"""
    memories: list[MemoryRead]
    total: int

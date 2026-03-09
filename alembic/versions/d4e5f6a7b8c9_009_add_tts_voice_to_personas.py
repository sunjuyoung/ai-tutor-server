"""009_add_tts_voice_to_personas

Phase 3.5: 페르소나별 TTS 음성 설정
- personas 테이블에 tts_voice 컬럼 추가
- 기본값: 'nova' (OpenAI TTS voice)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """personas 테이블에 tts_voice 컬럼 추가."""
    op.add_column(
        "personas",
        sa.Column("tts_voice", sa.String(20), nullable=False, server_default="nova"),
    )


def downgrade() -> None:
    """tts_voice 컬럼 제거."""
    op.drop_column("personas", "tts_voice")

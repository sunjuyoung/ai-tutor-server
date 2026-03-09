"""006_create_persona_memories

Phase 3 (W12~W13): 페르소나 기억 시스템
- pgvector 확장 활성화
- persona_memories 테이블 생성
- ivfflat 인덱스 (벡터 유사도 검색용)
- conversations 테이블에 is_benchmark 컬럼 추가

Revision ID: a1b2c3d4e5f6
Revises: 660d57498ae1
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "660d57498ae1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector 확장 활성화 (이미 설치되어 있어야 함)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # persona_memories 테이블 생성
    op.create_table(
        "persona_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("persona_id", sa.Uuid(), sa.ForeignKey("personas.id"), nullable=False),
        sa.Column("memory_type", sa.String(30), nullable=False),
        sa.Column("content", sa.String(500), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "source_conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=True,
        ),
        sa.Column("last_referenced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # 인덱스 생성
    op.create_index("ix_persona_memories_user_id", "persona_memories", ["user_id"])
    op.create_index("ix_persona_memories_persona_id", "persona_memories", ["persona_id"])

    # ivfflat 벡터 인덱스 (코사인 유사도 검색 최적화)
    # lists=100은 데이터 수가 적을 때도 동작, 데이터 증가 시 조정 필요
    op.execute(
        """
        CREATE INDEX ix_persona_memories_embedding
        ON persona_memories
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # conversations 테이블에 is_benchmark 컬럼 추가
    op.add_column(
        "conversations",
        sa.Column("is_benchmark", sa.Boolean(), nullable=True, server_default="false"),
    )
    op.execute("UPDATE conversations SET is_benchmark = false WHERE is_benchmark IS NULL")
    op.alter_column("conversations", "is_benchmark", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "is_benchmark")
    op.drop_table("persona_memories")
    op.execute("DROP EXTENSION IF EXISTS vector")

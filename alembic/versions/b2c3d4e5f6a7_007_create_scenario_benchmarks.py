"""007_create_scenario_benchmarks

Phase 3 (W14): Before/After 학습 효과 측정
- scenario_benchmarks 테이블 생성
- 유저×시나리오별 라운드 기록 저장

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "scenario_benchmarks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), sa.ForeignKey("scenarios.id"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("grammar_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_expressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fluency_score", sa.Integer(), nullable=True),
        sa.Column("response_time_avg", sa.Float(), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("persona_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # 유저×시나리오별 벤치마크 조회 인덱스
    op.create_index("ix_benchmarks_user_id", "scenario_benchmarks", ["user_id"])
    op.create_index("ix_benchmarks_scenario_id", "scenario_benchmarks", ["scenario_id"])
    op.create_index(
        "ix_benchmarks_user_scenario",
        "scenario_benchmarks",
        ["user_id", "scenario_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("scenario_benchmarks")

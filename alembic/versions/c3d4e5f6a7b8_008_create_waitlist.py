"""008_create_waitlist

Phase 3 (W15): Waitlist + 레퍼럴 시스템
- waitlist 테이블 생성
- 이메일 유니크 인덱스, 레퍼럴 코드 유니크 인덱스

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("interested_languages", sa.String(20), nullable=True),
        sa.Column("interested_situation", sa.String(50), nullable=True),
        sa.Column("referral_code", sa.String(20), nullable=False, unique=True),
        sa.Column("referred_by", sa.String(20), nullable=True),
        sa.Column("referral_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_waitlist_email", "waitlist", ["email"], unique=True)
    op.create_index("ix_waitlist_referral_code", "waitlist", ["referral_code"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("waitlist")

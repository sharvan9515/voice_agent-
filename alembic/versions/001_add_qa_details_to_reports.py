"""add qa_details to interview_reports

Revision ID: 001_qa_details
Revises:
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001_qa_details"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_reports",
        sa.Column("qa_details", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_reports", "qa_details")
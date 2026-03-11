"""add job table and resume fields

Revision ID: 002
Revises: 001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column(
            "description_parsed",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("candidates", sa.Column("resume_raw", sa.Text(), nullable=True))
    op.add_column(
        "candidates",
        sa.Column(
            "resume_parsed",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_session_job",
        "interview_sessions",
        "jobs",
        ["job_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_session_job", "interview_sessions", type_="foreignkey")
    op.drop_column("interview_sessions", "job_id")
    op.drop_column("candidates", "resume_parsed")
    op.drop_column("candidates", "resume_raw")
    op.drop_table("jobs")

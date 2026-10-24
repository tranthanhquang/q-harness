"""Generated reports and local artifact metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0005_reports"
down_revision = "0004_report_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(2048), unique=True, nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_record_id", sa.Uuid(), sa.ForeignKey("report_templates.id"), nullable=False
        ),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column("template_version", sa.String(50), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), sa.ForeignKey("artifacts.id")),
        sa.Column("missing_data", sa.JSON(), nullable=False),
        sa.Column("data_provenance", sa.JSON(), nullable=False),
        sa.Column("validation_evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("artifacts")

"""Read-only report template catalog."""

import sqlalchemy as sa
from alembic import op

revision = "0004_report_catalog"
down_revision = "0003_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope_project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("output_format", sa.String(10), nullable=False),
        sa.Column("contract_path", sa.String(2048), nullable=False),
        sa.Column("template_path", sa.String(2048), nullable=False),
        sa.Column("contract_sha256", sa.String(64), nullable=False),
        sa.Column("template_sha256", sa.String(64), nullable=False),
        sa.Column("license", sa.String(100), nullable=False),
        sa.Column("trusted", sa.Boolean(), nullable=False),
        sa.Column("contract", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope_project_id", "template_id", "version", name="uq_report_template_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("report_templates")

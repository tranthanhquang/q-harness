"""Snapshot operator-approved gates; existing tasks remain unable to pass without gates."""

import sqlalchemy as sa
from alembic import op

revision = "0007_required_gates"
down_revision = "0006_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("required_gates", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade() -> None:
    op.drop_column("tasks", "required_gates")

"""Task, execution and evidence records."""

import sqlalchemy as sa
from alembic import op

revision = "0003_tasks"
down_revision = "0002_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("risk", sa.String(30), nullable=False),
        sa.Column("workflow", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_item_id",
            sa.Uuid(),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_id", sa.String(30), unique=True, nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "task_repositories",
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "execution_repositories",
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("before_sha", sa.String(64)),
        sa.Column("after_sha", sa.String(64)),
    )
    op.create_table(
        "execution_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_execution_event_sequence"),
    )
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool", sa.String(100), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repository_id", sa.Uuid(), sa.ForeignKey("repositories.id", ondelete="CASCADE")),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("returncode", sa.Integer()),
        sa.Column("stdout", sa.Text(), nullable=False),
        sa.Column("stderr", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "test_runs",
        "tool_invocations",
        "execution_events",
        "execution_repositories",
        "executions",
        "approvals",
        "task_repositories",
        "tasks",
        "work_items",
    ):
        op.drop_table(table)

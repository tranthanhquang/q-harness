"""Audit immutability and execution concurrency safeguards."""

import sqlalchemy as sa
from alembic import op

revision = "0006_skills"
down_revision = "0005_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("canonical_path", sa.String(2048), nullable=False),
        sa.Column("source", sa.String(2048), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("license", sa.String(100), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("file_checksums", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "name",
            "version",
            name="uq_skill_scope_version",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_skill_records_project_id", "skill_records", ["project_id"])
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "search_vector")
    op.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN search_vector tsvector GENERATED"
        " ALWAYS AS (to_tsvector('simple', regexp_replace(coalesce(content, ''), "
        "'[^[:alnum:]]+', ' ', 'g'))) STORED"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_search_vector ON knowledge_chunks USING"
        " gin (search_vector)"
    )
    op.add_column("projects", sa.Column("stable_key", sa.String(64)))
    op.execute("UPDATE projects SET stable_key = 'project-' || replace(id::text, '-', '')")
    op.alter_column("projects", "stable_key", nullable=False)
    op.create_unique_constraint("uq_projects_stable_key", "projects", ["stable_key"])
    op.add_column(
        "repositories",
        sa.Column("access_mode", sa.String(20), nullable=False, server_default="READ_WRITE"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id")),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("reports.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_project_created", "audit_events", ["project_id", "created_at"])
    op.add_column(
        "audit_events", sa.Column("event_id", sa.BigInteger(), sa.Identity(), nullable=False)
    )
    op.create_unique_constraint("uq_audit_events_event_id", "audit_events", ["event_id"])
    op.execute("CREATE SEQUENCE task_display_sequence")
    op.execute(
        "SELECT setval('task_display_sequence', GREATEST(COALESCE((SELECT "
        "max(substring(display_id from '[0-9]+$')::bigint) FROM tasks WHERE "
        "display_id ~ '^QH-T-[0-9]+$'), 0) + 1, 1), false)"
    )
    op.create_index(
        "uq_execution_active_task",
        "executions",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('QUEUED', 'RUNNING')"),
    )
    op.execute(
        "CREATE FUNCTION deny_audit_mutation() RETURNS trigger LANGUAGE plpgsql "
        "AS $$ BEGIN RAISE EXCEPTION 'audit records are append-only'; END $$"
    )
    for table in ("audit_events", "execution_events", "approvals"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation()"
        )


def downgrade() -> None:
    op.drop_table("skill_records")
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "search_vector")
    op.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN search_vector tsvector GENERATED"
        " ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_search_vector ON knowledge_chunks USING"
        " gin (search_vector)"
    )
    for table in ("audit_events", "execution_events", "approvals"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION deny_audit_mutation()")
    op.drop_index("uq_execution_active_task", table_name="executions")
    op.execute("DROP SEQUENCE task_display_sequence")
    op.drop_table("audit_events")
    op.drop_column("repositories", "access_mode")
    op.drop_constraint("uq_projects_stable_key", "projects")
    op.drop_column("projects", "stable_key")

"""Enforce Project ownership across aggregate and evidence references."""

import sqlalchemy as sa
from alembic import op

revision = "0008_project_ownership"
down_revision = "0007_required_gates"
branch_labels = None
depends_on = None

SCOPED_TABLES = ("repositories", "work_items", "tasks", "executions", "artifacts", "reports")
LINKS = (
    ("tasks", "work_item", "work_items", ["work_item_id"], ["id"]),
    ("executions", "task", "tasks", ["task_id"], ["id"]),
    ("task_repositories", "task", "tasks", ["task_id"], ["id"]),
    ("task_repositories", "repository", "repositories", ["repository_id"], ["id"]),
    ("execution_repositories", "execution", "executions", ["execution_id"], ["id"]),
    ("execution_repositories", "repository", "repositories", ["repository_id"], ["id"]),
    ("index_versions", "repository", "repositories", ["repository_id"], ["id"]),
    ("source_files", "repository", "repositories", ["repository_id"], ["id"]),
    (
        "knowledge_chunks",
        "source",
        "source_files",
        ["repository_id", "source_file_id"],
        ["repository_id", "id"],
    ),
    (
        "symbols",
        "source",
        "source_files",
        ["repository_id", "source_file_id"],
        ["repository_id", "id"],
    ),
    ("reports", "artifact", "artifacts", ["artifact_id"], ["id"]),
    ("audit_events", "task", "tasks", ["task_id"], ["id"]),
    ("audit_events", "report", "reports", ["report_id"], ["id"]),
)


def upgrade() -> None:
    for table in SCOPED_TABLES:
        op.create_unique_constraint(f"uq_{table}_project_id", table, ["project_id", "id"])
    op.create_unique_constraint(
        "uq_source_files_project_repository_id",
        "source_files",
        ["project_id", "repository_id", "id"],
    )
    for table, parent, key in (
        ("task_repositories", "tasks", "task_id"),
        ("execution_repositories", "executions", "execution_id"),
    ):
        op.add_column(table, sa.Column("project_id", sa.Uuid()))
        link = sa.table(table, sa.column("project_id"), sa.column(key))
        owner = sa.table(parent, sa.column("id"), sa.column("project_id"))
        op.execute(
            link.update().values(project_id=owner.c.project_id).where(link.c[key] == owner.c.id)
        )
        op.alter_column(table, "project_id", nullable=False)
    for table, label, target, columns, remote in LINKS:
        op.create_foreign_key(
            f"fk_{table}_{label}_scope",
            table,
            target,
            ["project_id", *columns],
            ["project_id", *remote],
            ondelete=None if table in {"audit_events", "reports"} else "CASCADE",
        )
    op.create_foreign_key(
        "fk_test_runs_repository_scope",
        "test_runs",
        "execution_repositories",
        ["execution_id", "repository_id"],
        ["execution_id", "repository_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_report_template_version", "report_templates")
    op.create_unique_constraint(
        "uq_report_template_version",
        "report_templates",
        ["scope_project_id", "template_id", "version"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint("uq_report_template_version", "report_templates")
    op.create_unique_constraint(
        "uq_report_template_version",
        "report_templates",
        ["scope_project_id", "template_id", "version"],
    )
    op.drop_constraint("fk_test_runs_repository_scope", "test_runs")
    for table, label, *_ in reversed(LINKS):
        op.drop_constraint(f"fk_{table}_{label}_scope", table)
    for table in ("task_repositories", "execution_repositories"):
        op.drop_column(table, "project_id")
    op.drop_constraint("uq_source_files_project_repository_id", "source_files")
    for table in reversed(SCOPED_TABLES):
        op.drop_constraint(f"uq_{table}_project_id", table)

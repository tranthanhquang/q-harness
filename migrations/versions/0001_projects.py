"""Project and repository ownership."""

import sqlalchemy as sa
from alembic import op

revision = "0001_projects"
down_revision = "0000_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("workspace_path", sa.String(2048), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("workspace_path", name="uq_projects_workspace_path"),
    )
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("canonical_path", sa.String(2048), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_repositories_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
        sa.UniqueConstraint("canonical_path", name="uq_repositories_canonical_path"),
        sa.UniqueConstraint("project_id", "name", name="uq_repositories_project_name"),
    )
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_repositories_project_id", table_name="repositories")
    op.drop_table("repositories")
    op.drop_table("projects")

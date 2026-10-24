from __future__ import annotations

import builtins
import re
import uuid
from pathlib import Path

from sqlalchemy import select

from qharness.domain.errors import NotFound
from qharness.infrastructure.database import Database
from qharness.projects.config import read_project_id, write_project_config
from qharness.projects.models import Project, Repository
from qharness.security.paths import canonical_directory, find_project_file


class DuplicateRepository(ValueError):
    pass


class ProjectService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, name: str, workspace: Path, stable_key: str | None = None) -> Project:
        if not name.strip() or len(name) > 120:
            raise ValueError("Project name must contain 1 to 120 characters")
        key = stable_key or f"project-{uuid.uuid4().hex[:12]}"
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", key):
            raise ValueError("invalid Project stable key")
        workspace.mkdir(parents=True, exist_ok=True)
        canonical = canonical_directory(workspace)
        with self.database.transaction() as session:
            existing = session.scalar(
                select(Project).where(Project.workspace_path == str(canonical))
            )
            if existing:
                return existing
            project = Project(name=name, workspace_path=str(canonical), stable_key=key)
            session.add(project)
            session.flush()
            write_project_config(canonical, project.id, name)
            return project

    def add_repository(
        self,
        project_id: uuid.UUID,
        path: Path,
        role: str,
        name: str,
        access_mode: str = "READ_WRITE",
    ) -> Repository:
        if (
            access_mode not in {"READ_ONLY", "READ_WRITE"}
            or not name.strip()
            or len(name) > 120
            or not role.strip()
            or len(role) > 64
        ):
            raise ValueError("invalid repository name, role or access mode")
        canonical = canonical_directory(path)
        with self.database.transaction() as session:
            project = session.get(Project, project_id)
            if not project:
                raise NotFound("project not found")
            existing = session.scalar(
                select(Repository).where(Repository.canonical_path == str(canonical))
            )
            if existing:
                raise DuplicateRepository("repository path is already registered")
            repository = Repository(
                project_id=project_id,
                canonical_path=str(canonical),
                role=role,
                name=name,
                access_mode=access_mode,
            )
            session.add(repository)
            session.flush()
            return repository

    def get(self, project_id: uuid.UUID) -> Project:
        with self.database.transaction() as session:
            project = session.get(Project, project_id)
            if not project:
                raise NotFound("project not found")
            return project

    def list(self) -> list[Project]:
        with self.database.transaction() as session:
            return list(session.scalars(select(Project).order_by(Project.created_at)))

    def repositories(self, project_id: uuid.UUID) -> builtins.list[Repository]:
        with self.database.transaction() as session:
            return list(
                session.scalars(
                    select(Repository)
                    .where(Repository.project_id == project_id)
                    .order_by(Repository.name)
                )
            )

    def discover(self, start: Path) -> Project:
        config = find_project_file(start)
        if not config:
            raise NotFound("no active project for this directory")
        return self.get(read_project_id(config))

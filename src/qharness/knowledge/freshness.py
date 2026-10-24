from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select

from qharness.infrastructure.database import Database
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.models import SourceFile
from qharness.security.paths import contained_path


class KnowledgeFreshness:
    def __init__(self, database: Database) -> None:
        self.database = database

    def stale_paths(
        self, project_id: uuid.UUID, repository_id: uuid.UUID, root: Path
    ) -> list[Path]:
        with self.database.transaction() as session:
            sources = list(
                session.scalars(
                    select(SourceFile).where(
                        SourceFile.project_id == project_id,
                        SourceFile.repository_id == repository_id,
                    )
                )
            )
        stale: list[Path] = []
        for source in sources:
            try:
                absolute = contained_path(root, root / source.path)
                changed = (
                    not absolute.is_file()
                    or hashlib.sha256(absolute.read_bytes()).hexdigest() != source.content_hash
                )
            except (OSError, ValueError):
                changed = True
            if changed:
                stale.append(Path(source.path))
        return stale

    def refresh(self, project_id: uuid.UUID, repository_id: uuid.UUID, root: Path) -> list[Path]:
        return KnowledgeIndexer(self.database).refresh_repository(project_id, repository_id, root)

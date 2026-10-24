from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select

from qharness.infrastructure.database import Database
from qharness.knowledge.discovery import discover_file_metadata
from qharness.knowledge.models import IndexVersion, KnowledgeChunk, SourceFile, Symbol
from qharness.knowledge.parsers import extract_symbols
from qharness.projects.models import Repository
from qharness.security.paths import contained_path


class KnowledgeIndexer:
    def __init__(self, database: Database, chunk_lines: int = 200) -> None:
        self.database = database
        self.chunk_lines = chunk_lines

    def index_repository(
        self, project_id: uuid.UUID, repository_id: uuid.UUID, root: Path, *, full: bool = False
    ) -> list[Path]:
        with self.database.transaction() as session:
            repository = session.get(Repository, repository_id)
            if (
                not repository
                or repository.project_id != project_id
                or Path(repository.canonical_path) != root
                or root.is_symlink()
            ):
                raise PermissionError("repository is outside Project scope or has moved")
            previous = {
                source.path: source
                for source in session.scalars(
                    select(SourceFile).where(
                        SourceFile.repository_id == repository_id,
                        SourceFile.project_id == project_id,
                    )
                )
            }
            initial_version = IndexVersion(project_id=project_id, repository_id=repository_id)
            session.add(initial_version)
            session.flush()
            version_id = initial_version.id
        changed: list[Path] = []
        try:
            discovered = discover_file_metadata(
                root,
                known_files=None
                if full
                else {
                    name: (source.size_bytes, source.modified_ns)
                    for name, source in previous.items()
                },
            )
            names = set(discovered)
            for name in sorted(discovered):
                relative = Path(name)
                size, modified = discovered[name]
                old = previous.get(name)
                if not full and old and (old.size_bytes, old.modified_ns) == (size, modified):
                    continue
                absolute = contained_path(root, root / relative)
                raw = absolute.read_bytes()
                fingerprint = hashlib.sha256(raw).hexdigest()
                content = raw.decode("utf-8")
                parsed = extract_symbols(relative.as_posix(), content)
                with self.database.transaction() as session:
                    source = session.get(SourceFile, old.id) if old else None
                    if source is None:
                        source = SourceFile(
                            project_id=project_id,
                            repository_id=repository_id,
                            path=relative.as_posix(),
                        )
                        session.add(source)
                    source.content_hash, source.size_bytes = fingerprint, len(raw)
                    source.modified_ns, source.indexed_at = modified, datetime.now(UTC)
                    session.flush()
                    session.execute(
                        delete(KnowledgeChunk).where(KnowledgeChunk.source_file_id == source.id)
                    )
                    session.execute(delete(Symbol).where(Symbol.source_file_id == source.id))
                    lines = content.splitlines()
                    for offset in range(0, max(len(lines), 1), self.chunk_lines):
                        selected = lines[offset : offset + self.chunk_lines]
                        session.add(
                            KnowledgeChunk(
                                project_id=project_id,
                                repository_id=repository_id,
                                source_file_id=source.id,
                                start_line=offset + 1,
                                end_line=offset + max(len(selected), 1),
                                content="\n".join(selected),
                            )
                        )
                    for symbol in parsed:
                        session.add(
                            Symbol(
                                project_id=project_id,
                                repository_id=repository_id,
                                source_file_id=source.id,
                                name=symbol.name,
                                kind=symbol.kind,
                                line=symbol.line,
                            )
                        )
                    if (
                        hashlib.sha256(
                            contained_path(root, root / relative).read_bytes()
                        ).hexdigest()
                        != fingerprint
                    ):
                        raise OSError("source changed while indexing")
                changed.append(relative)
            with self.database.transaction() as session:
                for name, source in previous.items():
                    if name not in names:
                        session.execute(delete(SourceFile).where(SourceFile.id == source.id))
                        changed.append(Path(name))
                version = session.get(IndexVersion, version_id)
                assert version
                version.state = "COMPLETE"
        except Exception:
            with self.database.transaction() as session:
                version = session.get(IndexVersion, version_id)
                assert version
                version.state = "STALE"
            raise
        return changed

    def refresh_repository(
        self, project_id: uuid.UUID, repository_id: uuid.UUID, root: Path
    ) -> list[Path]:
        return self.index_repository(project_id, repository_id, root)

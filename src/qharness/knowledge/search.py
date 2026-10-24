from __future__ import annotations

import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, literal_column, select
from sqlalchemy.sql.elements import ColumnElement

from qharness.infrastructure.database import Database
from qharness.knowledge.discovery import discover_file_metadata
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.models import IndexVersion, KnowledgeChunk, SourceFile, Symbol
from qharness.projects.git import inspect_repository
from qharness.projects.service import ProjectService
from qharness.security.paths import contained_path


class StaleKnowledge(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SearchResult:
    repository_id: uuid.UUID
    path: str
    start_line: int
    end_line: int
    content: str
    content_hash: str
    symbol: str | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    index_status: str = "FRESH"

    def public(self) -> dict[str, Any]:
        from qharness.security.redaction import redact

        return {
            "repository_id": str(self.repository_id),
            "relative_path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "excerpt": redact(self.content[:4000]),
            "content_hash": self.content_hash,
            "symbol": self.symbol,
            "branch_name": self.branch_name,
            "commit_sha": self.commit_sha,
            "index_status": self.index_status,
        }


class KnowledgeSearch:
    def __init__(self, database: Database) -> None:
        self.database = database

    def search(
        self,
        project_id: uuid.UUID,
        query: str,
        limit: int = 20,
        repository_id: uuid.UUID | None = None,
        *,
        repository_ids: list[uuid.UUID] | None = None,
    ) -> list[SearchResult]:
        if not query.strip() or len(query) > 1000 or not 1 <= limit <= 50:
            raise ValueError("query must contain 1 to 1000 characters and limit must be 1 to 50")
        projects = ProjectService(self.database)
        projects.get(project_id)
        repositories = projects.repositories(project_id)
        selected = set(repository_ids or ([repository_id] if repository_id else []))
        if len(selected) > 20 or selected - {repo.id for repo in repositories}:
            raise PermissionError("repository is outside Project scope")
        if selected:
            repositories = [repo for repo in repositories if repo.id in selected]
        roots = {repo.id: Path(repo.canonical_path) for repo in repositories}
        try:
            # Overlap filesystem reads across repositories; keep index writes sequential.
            with ThreadPoolExecutor(max_workers=4) as executor:
                checks = [
                    executor.submit(self._is_dirty, project_id, repo.id, roots[repo.id])
                    for repo in repositories
                ]
                dirty_repositories = [check.result() for check in checks]
            for repo, dirty in zip(repositories, dirty_repositories, strict=True):
                if dirty:
                    KnowledgeIndexer(self.database).refresh_repository(
                        project_id, repo.id, roots[repo.id]
                    )
            return self._retrieve(project_id, query, limit, roots)
        except (OSError, UnicodeError, ValueError) as exc:
            raise StaleKnowledge(
                "Index is stale; restore repository access and run qh project refresh"
            ) from exc

    def _is_dirty(self, project_id: uuid.UUID, repository_id: uuid.UUID, root: Path) -> bool:
        if root.is_symlink():
            raise StaleKnowledge("registered repository root was replaced")
        with self.database.transaction() as session:
            sources = {
                name: (size, modified)
                for name, size, modified in session.execute(
                    select(SourceFile.path, SourceFile.size_bytes, SourceFile.modified_ns).where(
                        SourceFile.project_id == project_id,
                        SourceFile.repository_id == repository_id,
                    )
                )
            }
            latest = session.scalar(
                select(IndexVersion)
                .where(IndexVersion.repository_id == repository_id)
                .order_by(IndexVersion.created_at.desc())
                .limit(1)
            )
        return (
            not latest
            or latest.state != "COMPLETE"
            or discover_file_metadata(root, known_files=sources) != sources
        )

    def _retrieve(
        self, project_id: uuid.UUID, query: str, limit: int, roots: dict[uuid.UUID, Path]
    ) -> list[SearchResult]:
        terms = re.findall(r"[^\W_]+", query, re.UNICODE)
        if not terms:
            return []
        with self.database.transaction() as session:
            vector: ColumnElement[Any] = literal_column("knowledge_chunks.search_vector")
            tsquery = func.plainto_tsquery("simple", " ".join(terms))
            rows = session.execute(
                select(KnowledgeChunk, SourceFile)
                .join(SourceFile, SourceFile.id == KnowledgeChunk.source_file_id)
                .where(
                    KnowledgeChunk.project_id == project_id,
                    KnowledgeChunk.repository_id.in_(roots),
                    vector.op("@@")(tsquery),
                )
                .order_by(
                    func.ts_rank(vector, tsquery).desc(), SourceFile.path, KnowledgeChunk.start_line
                )
                .limit(limit)
            ).all()
            results = [
                SearchResult(
                    chunk.repository_id,
                    source.path,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.content,
                    source.content_hash,
                )
                for chunk, source in rows
            ]
            if len(results) < limit:
                symbols = session.execute(
                    select(Symbol, SourceFile)
                    .join(SourceFile, SourceFile.id == Symbol.source_file_id)
                    .where(
                        Symbol.project_id == project_id,
                        Symbol.repository_id.in_(roots),
                        and_(*(Symbol.name.ilike(f"%{term}%", escape="\\") for term in terms)),
                    )
                    .order_by(SourceFile.path, Symbol.line)
                    .limit(limit)
                ).all()
                known = {(item.repository_id, item.path, item.start_line) for item in results}
                for symbol, source in symbols:
                    if len(results) >= limit:
                        break
                    if (symbol.repository_id, source.path, symbol.line) not in known:
                        results.append(
                            SearchResult(
                                symbol.repository_id,
                                source.path,
                                symbol.line,
                                symbol.line,
                                symbol.name,
                                source.content_hash,
                                symbol.name,
                            )
                        )
        from dataclasses import replace

        git = {identity: inspect_repository(root) for identity, root in roots.items()}
        for result in results:
            path = contained_path(
                roots[result.repository_id], roots[result.repository_id] / result.path
            )
            if hashlib.sha256(path.read_bytes()).hexdigest() != result.content_hash:
                raise StaleKnowledge("source changed during search; run qh project refresh")
        return [
            replace(
                result,
                branch_name=git[result.repository_id].branch,
                commit_sha=git[result.repository_id].head,
            )
            for result in results
        ]

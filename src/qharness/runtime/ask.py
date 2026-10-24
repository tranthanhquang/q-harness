from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AskAnswer:
    text: str
    citations: tuple[dict[str, Any], ...]
    stale: bool = False


class AskService:
    allowed_tools = ("knowledge_search", "project_get")

    def __init__(self, search: Any) -> None:
        self.search = search

    def ask(self, project_id: uuid.UUID, question: str) -> AskAnswer:
        results = self.search.search(project_id, question, limit=5)
        if not results:
            return AskAnswer("Không tìm thấy nguồn phù hợp.", ())
        citations = tuple(
            {
                **item.public(),
                "repository_id": str(item.repository_id),
                "path": item.path,
                "line": item.start_line,
                "content_hash": item.content_hash,
            }
            for item in results
        )
        first = results[0]
        return AskAnswer(
            f"Nguồn liên quan: {first.path}:{first.start_line} — {first.content[:160]}", citations
        )

import uuid

from qharness.runtime.ask import AskService


class FakeSearch:
    def search(self, project_id: uuid.UUID, query: str, limit: int = 5):
        from qharness.knowledge.search import SearchResult

        return [SearchResult(uuid.uuid4(), "service.py", 1, 2, "def health(): pass", "abc")]


def test_ask_is_concise_sourced_and_has_no_write_registry() -> None:
    service = AskService(FakeSearch())
    answer = service.ask(uuid.uuid4(), "Where is health?")
    assert "service.py:1" in answer.text
    assert answer.citations[0]["path"] == "service.py"
    assert set(service.allowed_tools) == {"knowledge_search", "project_get"}

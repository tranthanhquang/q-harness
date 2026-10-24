import json

import httpx
import pytest
from openai import OpenAI

from qharness.runtime import providers


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        (None, "https://api.openai.com/v1/responses"),
        ("https://gateway.example/api/v1/", "https://gateway.example/api/v1/responses"),
    ],
)
def test_provider_routes_responses_request(
    monkeypatch: pytest.MonkeyPatch, base_url: str | None, expected_url: str
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == expected_url
        assert request.headers["authorization"] == "Bearer test-provider-key"
        assert json.loads(request.content) == {
            "model": "provider/model-name",
            "instructions": "Return a JSON action",
            "input": "Fix demo",
            "tools": [],
        }
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "provider/model-name",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_test",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": '{"tool":"finish"}', "annotations": []}
                        ],
                    }
                ],
            },
        )

    monkeypatch.setenv("OPENAI_BASE_URL", "https://unselected.example/v1")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        monkeypatch.setattr(
            providers,
            "OpenAI",
            lambda **kwargs: OpenAI(http_client=client, **kwargs),
        )
        provider = providers.OpenAIResponsesProvider(
            "provider/model-name", "test-provider-key", base_url=base_url
        )
        assert provider.respond("Return a JSON action", "Fix demo") == '{"tool":"finish"}'

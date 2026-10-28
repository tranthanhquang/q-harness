import json
from pathlib import Path
from subprocess import CompletedProcess

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


def test_codex_provider_reuses_device_login_without_exposing_other_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / ".codex"
    config.mkdir()
    (config / "config.toml").write_text('model = "device-model"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", "/other-codex-home")
    monkeypatch.setenv("CODEX_API_KEY", "separate-key")
    monkeypatch.setenv("OPENAI_API_KEY", "other-key")
    monkeypatch.setattr(providers.shutil, "which", lambda _: "/usr/local/bin/codex")

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        assert command[:3] == ["/usr/local/bin/codex", "-a", "never"]
        assert command[command.index("-m") + 1] == "device-model"
        assert "--ignore-user-config" in command
        assert 'default_permissions="qh_read"' in command
        assert (
            'permissions.qh_read.filesystem={":root"="deny",":minimal"="read",":tmpdir"="deny",":slash_tmp"="deny"}'
            in command
        )
        assert "--ephemeral" in command
        schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        assert set(schema["required"]) == set(schema["properties"])
        assert kwargs["env"] is not None
        assert all(
            name not in kwargs["env"] for name in ("CODEX_HOME", "CODEX_API_KEY", "OPENAI_API_KEY")
        )
        assert "Return JSON" in kwargs["input"]
        return CompletedProcess(command, 0, '{"tool":"finish"}', "")

    monkeypatch.setattr(providers.subprocess, "run", run)
    assert providers.CodexCLIProvider().respond("Return JSON", "Fix demo") == '{"tool":"finish"}'

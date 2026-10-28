from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Protocol

from openai import OpenAI
from openai.types.responses import ToolParam


class ModelProvider(Protocol):
    def respond(
        self, instructions: str, input: str, tools: list[ToolParam] | None = None
    ) -> str: ...


class OpenAIResponsesProvider:
    def __init__(self, model: str, api_key: str, *, base_url: str | None = None) -> None:
        if not model:
            raise ValueError("model must be explicit")
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")

    def respond(self, instructions: str, input: str, tools: list[ToolParam] | None = None) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=input,
            tools=tools or [],
        )
        return response.output_text


class CodexCLIProvider:
    def __init__(self) -> None:
        config_path = Path.home() / ".codex" / "config.toml"
        self.model = (
            tomllib.loads(config_path.read_text()).get("model") if config_path.is_file() else None
        )

    def respond(self, instructions: str, input: str, tools: list[ToolParam] | None = None) -> str:
        if tools:
            raise ValueError("Codex CLI provider does not accept external tools")
        from qharness.runtime.agent import Action

        schema = Action.model_json_schema()
        schema["required"] = list(schema["properties"])
        for field in schema["properties"].values():
            field.pop("default", None)
        environment = os.environ.copy()
        for name in ("CODEX_HOME", "CODEX_API_KEY", "OPENAI_API_KEY"):
            environment.pop(name, None)
        codex = shutil.which("codex")
        if not codex:
            raise FileNotFoundError("Codex CLI is not installed on the worker PATH")
        with tempfile.TemporaryDirectory(prefix="qh-codex-") as directory:
            schema_path = Path(directory) / "action.json"
            schema_path.write_text(json.dumps(schema))
            command = [
                codex,
                "-a",
                "never",
                "-c",
                'default_permissions="qh_read"',
                "-c",
                'permissions.qh_read.extends=":read-only"',
                "-c",
                'permissions.qh_read.filesystem={":root"="deny",":minimal"="read",":tmpdir"="deny",":slash_tmp"="deny"}',
                "-c",
                "permissions.qh_read.network.enabled=false",
            ]
            if isinstance(self.model, str) and self.model:
                command.extend(["-m", self.model])
            command.extend(
                [
                    "exec",
                    "--ignore-user-config",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--output-schema",
                    str(schema_path),
                    "-",
                ]
            )
            # shortcut: one Codex process per action; use a persistent thread if latency matters.
            result = subprocess.run(  # noqa: S603 - fixed Codex arguments, no shell
                command,
                input=f"{instructions}\n\nInput:\n{input}",
                text=True,
                capture_output=True,
                cwd=directory,
                env=environment,
                timeout=300,
            )
            if result.returncode:
                raise RuntimeError("Codex CLI failed; check 'codex login status' and worker logs")
            return result.stdout.strip()

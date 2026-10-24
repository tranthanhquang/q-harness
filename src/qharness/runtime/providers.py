from __future__ import annotations

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

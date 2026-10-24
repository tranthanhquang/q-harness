from __future__ import annotations

from typing import Protocol

from openai import OpenAI
from openai.types.responses import ToolParam


class ModelProvider(Protocol):
    def respond(
        self, instructions: str, input: str, tools: list[ToolParam] | None = None
    ) -> str: ...


class OpenAIResponsesProvider:
    def __init__(self, model: str, api_key: str) -> None:
        if not model:
            raise ValueError("model must be explicit")
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def respond(self, instructions: str, input: str, tools: list[ToolParam] | None = None) -> str:
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=input,
            tools=tools or [],
        )
        return response.output_text

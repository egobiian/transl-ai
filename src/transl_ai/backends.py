"""Model backends: where a prompt is sent to get the model's reply."""

from collections.abc import Sequence
from typing import Protocol

import ollama

from transl_ai.config import DEFAULT_MODEL
from transl_ai.prompts import Message


class Backend(Protocol):
    def complete(self, messages: Sequence[Message]) -> str: ...


class OllamaBackend:
    def __init__(
        self, model: str = DEFAULT_MODEL, client: ollama.Client | None = None
    ) -> None:
        self._model = model
        self._client = client if client is not None else ollama.Client()

    def complete(self, messages: Sequence[Message]) -> str:
        response = self._client.chat(
            model=self._model,
            messages=messages,
            options={"temperature": 0},
        )
        return response.message.content or ""

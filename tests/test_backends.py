from collections.abc import Mapping, Sequence

import ollama
import pytest

from transl_ai.backends import OllamaBackend
from transl_ai.prompts import Message, build_messages


def test_ollama_backend_asks_the_model_deterministically_and_returns_its_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ollama.Client()
    calls: list[tuple[str, Sequence[Message], Mapping[str, object]]] = []

    def fake_chat(
        *, model: str, messages: Sequence[Message], options: Mapping[str, object]
    ) -> ollama.ChatResponse:
        calls.append((model, messages, options))
        return ollama.ChatResponse(
            message=ollama.Message(role="assistant", content="Play")
        )

    monkeypatch.setattr(client, "chat", fake_chat)
    messages = build_messages("Jugar", source="es", target="en")

    reply = OllamaBackend(model="some-model", client=client).complete(messages)

    assert reply == "Play"
    assert calls == [("some-model", messages, {"temperature": 0})]

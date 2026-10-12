import json
import threading
from collections.abc import Iterator, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anthropic
import ollama
import pytest

from transl_ai.backends import (
    AnthropicBackend,
    BackendError,
    OllamaBackend,
    OpenAIBackend,
)
from transl_ai.prompts import Message, build_messages

MESSAGES = build_messages("Jugar", source="es", target="en")
SYSTEM, USER = (message["content"] for message in MESSAGES)

OPENAI_REPLY = json.dumps({"choices": [{"message": {"content": "Play"}}]})


def claude_reply(text: str = "Play", stop_reason: str = "end_turn") -> str:
    return json.dumps(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )


class FakeApi(ThreadingHTTPServer):
    """A local stand-in for a model API: it records requests and replies as told."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), FakeApiHandler)
        self.replies: list[tuple[int, str]] = [(200, OPENAI_REPLY)]
        self.paths: list[str] = []
        self.headers: list[dict[str, str]] = []
        self.requests: list[dict[str, object]] = []

    @property
    def root(self) -> str:
        return f"http://127.0.0.1:{self.server_port}"

    def claude(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(api_key="secret", base_url=self.root, max_retries=0)


class FakeApiHandler(BaseHTTPRequestHandler):
    server: FakeApi

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        self.server.paths.append(self.path)
        self.server.headers.append({k.lower(): v for k, v in self.headers.items()})
        self.server.requests.append(json.loads(self.rfile.read(length)))
        # The last reply is repeated once the others have been given.
        replies = self.server.replies
        status, body = replies.pop(0) if len(replies) > 1 else replies[0]
        reply = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def api() -> Iterator[FakeApi]:
    server = FakeApi()
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


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

    reply = OllamaBackend(model="some-model", client=client).complete(MESSAGES)

    assert reply == "Play"
    assert calls == [("some-model", MESSAGES, {"temperature": 0})]


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (ConnectionError("refused"), "cannot reach Ollama"),
        (
            ollama.ResponseError("model 'some-model' not found", 404),
            "`ollama pull some-model`",
        ),
        (ollama.ResponseError("out of memory", 500), "error: out of memory"),
    ],
)
def test_ollama_failures_are_reported_with_what_to_do(
    failure: Exception, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = ollama.Client()

    def failing_chat(**_: object) -> ollama.ChatResponse:
        raise failure

    monkeypatch.setattr(client, "chat", failing_chat)

    with pytest.raises(BackendError, match=message):
        OllamaBackend(model="some-model", client=client).complete(MESSAGES)


def test_openai_backend_posts_the_chat_and_returns_the_reply(api: FakeApi) -> None:
    backend = OpenAIBackend("some-model", "secret", api.root + "/v1/")

    assert backend.complete(MESSAGES) == "Play"
    assert api.paths == ["/v1/chat/completions"]
    assert api.headers[0]["authorization"] == "Bearer secret"
    assert api.requests == [
        {"model": "some-model", "messages": MESSAGES, "temperature": 0}
    ]


def test_openai_backend_sends_no_key_when_it_has_none(api: FakeApi) -> None:
    OpenAIBackend("some-model", None, api.root + "/v1").complete(MESSAGES)

    assert "authorization" not in api.headers[0]


def test_a_model_that_refuses_the_temperature_is_asked_again_without_it(
    api: FakeApi,
) -> None:
    refusal = '{"error": {"message": "Unsupported value: temperature", "param": "x"}}'
    api.replies = [(400, refusal), (200, OPENAI_REPLY)]
    backend = OpenAIBackend("some-model", "secret", api.root + "/v1")

    assert backend.complete(MESSAGES) == "Play"
    assert backend.complete(MESSAGES) == "Play"

    assert ["temperature" in request for request in api.requests] == [
        True,
        False,
        False,
    ]


def test_a_request_the_api_refuses_is_reported_with_its_answer(api: FakeApi) -> None:
    api.replies = [(401, '{"error": "invalid api key"}')]

    with pytest.raises(BackendError, match=r"\(401\).*invalid api key"):
        OpenAIBackend("some-model", "wrong", api.root + "/v1").complete(MESSAGES)
    assert len(api.requests) == 1


def test_a_refusal_is_reported_on_one_line_with_the_message_inside_it(
    api: FakeApi,
) -> None:
    body = json.dumps(
        {"error": {"message": "Incorrect API key\nprovided.", "code": "x"}}, indent=4
    )
    api.replies = [(401, body)]

    with pytest.raises(BackendError) as excinfo:
        OpenAIBackend("some-model", "wrong", api.root + "/v1").complete(MESSAGES)

    assert str(excinfo.value) == (
        "the API refused the request (401): Incorrect API key provided."
    )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("<html>gateway</html>", "did not answer with JSON"),
        ('{"choices": []}', "answered without a message"),
        ('{"id": "x"}', "answered without a message"),
        ("[]", "answered without a message"),
    ],
)
def test_an_answer_that_is_not_a_chat_reply_is_reported(
    body: str, message: str, api: FakeApi
) -> None:
    api.replies = [(200, body)]

    with pytest.raises(BackendError, match=message):
        OpenAIBackend("some-model", None, api.root + "/v1").complete(MESSAGES)


def test_an_api_that_is_not_there_is_reported(api: FakeApi) -> None:
    url = api.root + "/v1"
    api.shutdown()
    api.server_close()

    with pytest.raises(BackendError, match="cannot reach the API"):
        OpenAIBackend("some-model", None, url).complete(MESSAGES)


def test_an_api_address_must_be_http() -> None:
    with pytest.raises(ValueError, match="not an http"):
        OpenAIBackend("some-model", None, "file:///etc/passwd")


def test_anthropic_backend_sends_the_rules_as_system_and_returns_the_text(
    api: FakeApi,
) -> None:
    api.replies = [(200, claude_reply("Play"))]

    reply = AnthropicBackend("claude-haiku-5-5", api.claude()).complete(MESSAGES)

    assert reply == "Play"
    assert api.paths == ["/v1/messages"]
    assert api.headers[0]["x-api-key"] == "secret"
    assert api.requests == [
        {
            "model": "claude-haiku-5-5",
            "max_tokens": 16000,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": USER}],
            "output_config": {"effort": "low"},
        }
    ]


@pytest.mark.parametrize(
    "model",
    ["claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"],
)
def test_a_model_with_a_refusal_fallback_is_asked_to_use_it(
    model: str, api: FakeApi
) -> None:
    api.replies = [(200, claude_reply())]

    AnthropicBackend(model, api.claude()).complete(MESSAGES)

    assert api.requests[0]["fallbacks"] == "default"
    assert api.requests[0]["output_config"] == {"effort": "low"}
    assert api.headers[0]["anthropic-beta"] == "server-side-fallback-2026-07-01"


def test_the_default_anthropic_model_is_the_current_opus(api: FakeApi) -> None:
    api.replies = [(200, claude_reply())]

    AnthropicBackend(client=api.claude()).complete(MESSAGES)

    assert api.requests[0]["model"] == "claude-opus-5-5"


def test_a_model_without_the_effort_setting_is_not_sent_it(api: FakeApi) -> None:
    api.replies = [(200, claude_reply())]

    AnthropicBackend("claude-haiku-4-5", api.claude()).complete(MESSAGES)

    assert sorted(api.requests[0]) == ["max_tokens", "messages", "model", "system"]
    assert "anthropic-beta" not in api.headers[0]


def test_no_claude_model_is_sent_a_temperature(api: FakeApi) -> None:
    api.replies = [(200, claude_reply())]

    for model in ("claude-opus-5-5", "claude-haiku-5-5", "claude-haiku-4-5"):
        AnthropicBackend(model, api.claude()).complete(MESSAGES)

    assert not any("temperature" in request for request in api.requests)


@pytest.mark.parametrize(
    ("status", "kind", "message"),
    [
        (401, "authentication_error", "rejected the API key"),
        (404, "not_found_error", "does not offer the model 'claude-opus-5-5'"),
        (429, "rate_limit_error", "rate limiting this key"),
        (400, "invalid_request_error", r"refused the request \(400\)"),
        (500, "api_error", r"refused the request \(500\)"),
    ],
)
def test_anthropic_failures_are_reported_with_what_to_do(
    status: int, kind: str, message: str, api: FakeApi
) -> None:
    error = {"type": "error", "error": {"type": kind, "message": "details"}}
    api.replies = [(status, json.dumps(error))]

    with pytest.raises(BackendError, match=message):
        AnthropicBackend(client=api.claude()).complete(MESSAGES)


@pytest.mark.parametrize(
    ("stop_reason", "message"),
    [("refusal", "declined to translate"), ("max_tokens", "cut off")],
)
def test_a_reply_that_is_not_a_whole_translation_is_reported(
    stop_reason: str, message: str, api: FakeApi
) -> None:
    api.replies = [(200, claude_reply("Pla", stop_reason))]

    with pytest.raises(BackendError, match=message):
        AnthropicBackend(client=api.claude()).complete(MESSAGES)


def test_anthropic_that_cannot_be_reached_is_reported(api: FakeApi) -> None:
    client = api.claude()
    api.shutdown()
    api.server_close()

    with pytest.raises(BackendError, match="cannot reach Anthropic"):
        AnthropicBackend(client=client).complete(MESSAGES)


def test_anthropic_without_credentials_is_reported_before_any_request(
    api: FakeApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    client = anthropic.Anthropic(base_url=api.root, max_retries=0)

    with pytest.raises(BackendError, match=r"put ANTHROPIC_API_KEY in a \.env file"):
        AnthropicBackend(client=client)
    assert api.requests == []

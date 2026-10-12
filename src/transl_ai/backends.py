"""Model backends: where a prompt is sent to get the model's reply."""

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Protocol

import anthropic
import ollama
from anthropic.types import Message as AnthropicMessage
from anthropic.types.beta import BetaMessage

from transl_ai.config import ANTHROPIC_MODEL, OLLAMA_MODEL, OPENAI_API
from transl_ai.prompts import Message

API_TIMEOUT_SECONDS = 120
ANTHROPIC_MAX_TOKENS = 16000

# Claude models do not all take the same request, so it is shaped for the one chosen.
# These re-run a request their safety classifiers decline on another model.
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
ANTHROPIC_WITH_FALLBACK = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)
# This one predates the effort setting and rejects it.
ANTHROPIC_WITHOUT_EFFORT = frozenset({"claude-haiku-4-5"})


class BackendError(Exception):
    """Raised when a backend cannot answer; the message is meant for the user."""


class Backend(Protocol):
    def complete(self, messages: Sequence[Message]) -> str: ...


class OllamaBackend:
    def __init__(
        self, model: str = OLLAMA_MODEL, client: ollama.Client | None = None
    ) -> None:
        self._model = model
        self._client = client if client is not None else ollama.Client()

    def complete(self, messages: Sequence[Message]) -> str:
        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options={"temperature": 0},
            )
        except ConnectionError as error:
            raise BackendError(
                "cannot reach Ollama: start it (open the app or run `ollama serve`)"
                " and try again"
            ) from error
        except ollama.ResponseError as error:
            if error.status_code == 404:
                raise BackendError(
                    f"Ollama does not have the model {self._model!r}: download it"
                    f" with `ollama pull {self._model}`"
                ) from error
            raise BackendError(f"Ollama answered with an error: {error}") from error
        return response.message.content or ""


class OpenAIBackend:
    """A model behind OpenAI's chat completions API, or one compatible with it."""

    def __init__(
        self, model: str, api_key: str | None = None, base_url: str = OPENAI_API
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError(f"not an http(s) address: {base_url!r}")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._fixed_temperature = True

    def complete(self, messages: Sequence[Message]) -> str:
        try:
            answer = self._post(messages)
        except _Rejected as error:
            # Some models only take their default temperature. The first refusal
            # that names it settles the question for the rest of the run.
            asked_for_it = self._fixed_temperature and error.status == 400
            if not (asked_for_it and "temperature" in error.detail):
                raise
            self._fixed_temperature = False
            answer = self._post(messages)
        choices = answer.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            raise BackendError(f"the API at {self._url} answered without a message")
        content = message.get("content")
        return content if isinstance(content, str) else ""

    def _post(self, messages: Sequence[Message]) -> dict[str, object]:
        body: dict[str, object] = {"model": self._model, "messages": list(messages)}
        if self._fixed_temperature:
            body["temperature"] = 0
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            self._url, data=json.dumps(body).encode("utf-8"), headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as reply:
                answer = json.load(reply)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise _Rejected(error.code, detail) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise BackendError(
                f"cannot reach the API at {self._url}: {error}"
            ) from error
        except json.JSONDecodeError as error:
            raise BackendError(
                f"the API at {self._url} did not answer with JSON"
            ) from error
        if not isinstance(answer, dict):
            raise BackendError(f"the API at {self._url} answered without a message")
        return answer


class AnthropicBackend:
    """A Claude model, through Anthropic's API."""

    def __init__(
        self, model: str = ANTHROPIC_MODEL, client: anthropic.Anthropic | None = None
    ) -> None:
        self._model = model
        self._client = client if client is not None else anthropic.Anthropic()
        found = (
            self._client.api_key,
            self._client.auth_token,
            self._client.credentials,
        )
        if not any(found):
            raise BackendError(
                "no Anthropic credentials: put ANTHROPIC_API_KEY in a .env file or"
                " in the environment"
            )

    def complete(self, messages: Sequence[Message]) -> str:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        text = "\n".join(m["content"] for m in messages if m["role"] == "user")
        try:
            response = self._send(system, text)
        except anthropic.AuthenticationError as error:
            raise BackendError(
                "Anthropic rejected the API key: check ANTHROPIC_API_KEY"
            ) from error
        except anthropic.NotFoundError as error:
            raise BackendError(
                f"Anthropic does not offer the model {self._model!r} to this key"
            ) from error
        except anthropic.RateLimitError as error:
            raise BackendError(
                "Anthropic is rate limiting this key: wait a moment and run again"
            ) from error
        except anthropic.APIStatusError as error:
            raise BackendError(
                f"Anthropic refused the request ({error.status_code}): {error.message}"
            ) from error
        except anthropic.APIConnectionError as error:
            raise BackendError(
                "cannot reach Anthropic: check the connection"
            ) from error
        if response.stop_reason == "refusal":
            raise BackendError("the model declined to translate a text")
        if response.stop_reason == "max_tokens":
            raise BackendError("the model's reply was cut off before its end")
        return "".join(block.text for block in response.content if block.type == "text")

    def _send(self, system: str, text: str) -> AnthropicMessage | BetaMessage:
        # A translation of a short text needs little reasoning: low effort keeps it
        # quick and cheap. No temperature is sent: current models reject it.
        if self._model in ANTHROPIC_WITH_FALLBACK:
            return self._client.beta.messages.create(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": text}],
                output_config={"effort": "low"},
                betas=[ANTHROPIC_FALLBACK_BETA],
                fallbacks="default",
            )
        if self._model in ANTHROPIC_WITHOUT_EFFORT:
            return self._client.messages.create(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": text}],
            )
        return self._client.messages.create(
            model=self._model,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": text}],
            output_config={"effort": "low"},
        )


class _Rejected(BackendError):
    """An API answered a request with an HTTP error."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"the API refused the request ({status}): {_reason(detail)}")
        self.status = status
        self.detail = detail


def _reason(detail: str) -> str:
    """The message inside an API's error reply, on one line."""
    try:
        error = json.loads(detail)
    except json.JSONDecodeError:
        error = None
    if isinstance(error, dict):
        error = error.get("error", error)
    if isinstance(error, dict):
        error = error.get("message")
    text = error if isinstance(error, str) else detail
    return " ".join(text.split())[:300]

from collections.abc import Sequence

import pytest

from transl_ai.godot_csv import Entry
from transl_ai.prompts import Message
from transl_ai.translator import translate, translate_entry


class RecordingBackend:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received: list[Sequence[Message]] = []

    def complete(self, messages: Sequence[Message]) -> str:
        self.received.append(messages)
        return self.reply

    @property
    def last_system_content(self) -> str:
        return self.received[-1][0]["content"]

    @property
    def last_user_content(self) -> str:
        return self.received[-1][-1]["content"]


def test_translate_entry_describes_the_row_to_the_model() -> None:
    backend = RecordingBackend("There is %d waitress in the tavern.")
    entry = Entry(
        row=7,
        key="TAVERN_STAFF",
        text="Hay %d camarera en la taberna.",
        context="female",
        plural_form=0,
    )

    result = translate_entry(backend, entry, source="es", target="en")

    assert result == "There is %d waitress in the tavern."
    assert backend.last_user_content.endswith("\n\n\nHay %d camarera en la taberna.")
    assert (
        "translation key TAVERN_STAFF; context: female;"
        " plural form: singular, %d is exactly 1" in backend.last_system_content
    )


def test_translate_returns_the_reply_without_surrounding_whitespace() -> None:
    backend = RecordingBackend("  Exit\n")

    assert translate(backend, "Salir", source="es", target="en") == "Exit"


def test_translate_sends_the_text_and_the_context_to_the_backend() -> None:
    backend = RecordingBackend("Exit")

    translate(
        backend,
        "Salir",
        source="es",
        target="en",
        context="translation key MENU_QUIT",
    )

    (messages,) = backend.received
    system, user = messages
    assert "translation key MENU_QUIT" in system["content"]
    assert user["content"].endswith("\n\n\nSalir")


@pytest.mark.parametrize(
    ("text", "reply", "expected"),
    [
        ("Jugar", "Play.", "Play"),
        ("Tienes %d moneda", "You have %d coin.", "You have %d coin"),
        (
            "¡Esto es pan comido!",
            "This is a piece of cake!",
            "This is a piece of cake!",
        ),
        ("Partida guardada.", "Game saved.", "Game saved."),
        ("Cargando", "Loading...", "Loading..."),
        ("Hace mucho tiempo...", "Long ago...", "Long ago..."),
    ],
)
def test_a_final_period_the_source_does_not_have_is_removed(
    text: str, reply: str, expected: str
) -> None:
    backend = RecordingBackend(reply)

    assert translate(backend, text, source="es", target="en") == expected


def test_newline_escapes_reach_the_model_as_line_breaks_and_come_back_escaped() -> None:
    backend = RecordingBackend("Game saved.\nDo not turn off the console.")

    result = translate(
        backend,
        r"Partida guardada.\nNo apagues la consola.",
        source="es",
        target="en",
    )

    assert backend.last_user_content.endswith(
        "\n\n\nPartida guardada.\nNo apagues la consola."
    )
    assert result == r"Game saved.\nDo not turn off the console."


def test_real_line_breaks_are_left_as_they_are() -> None:
    backend = RecordingBackend("Long ago,\nin a forgotten kingdom...")

    result = translate(
        backend,
        "Hace mucho tiempo,\nen un reino olvidado...",
        source="es",
        target="en",
    )

    assert backend.last_user_content.endswith(
        "\n\n\nHace mucho tiempo,\nen un reino olvidado..."
    )
    assert result == "Long ago,\nin a forgotten kingdom..."

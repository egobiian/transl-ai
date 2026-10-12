from collections.abc import Sequence
from pathlib import Path

import pytest

from transl_ai.godot_csv import Document, MissingLocaleError, read, write
from transl_ai.prompts import Message
from transl_ai.translator import translate, translate_document


class RecordingBackend:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.received: list[Sequence[Message]] = []

    def complete(self, messages: Sequence[Message]) -> str:
        self.received.append(messages)
        return self.reply

    @property
    def last_user_content(self) -> str:
        return self.received[-1][-1]["content"]


class EchoBackend:
    """Replies with the target language around the text, as `English(Jugar)`."""

    def __init__(self, replies: dict[str, str] | None = None) -> None:
        self.replies = replies or {}
        self.contexts: list[str] = []
        self.texts: list[str] = []

    def complete(self, messages: Sequence[Message]) -> str:
        system, user = messages
        self.contexts.append(system["content"].splitlines()[-1].split(": ", 1)[1])
        instructions, text = user["content"].split("\n\n\n", 1)
        self.texts.append(text)
        target = instructions.rsplit(" into ", 1)[1].rstrip(":")
        return self.replies.get(text, f"{target}({text})")


PLURALS = (
    "keys,?plural,?context,es\n"
    "?pluralrule,,,nplurals=2; plural=(n != 1);\n"
    "PLAY,,,Jugar\n"
    "STAFF,STAFF_PLURAL,female,Hay %d camarera.\n"
    ",,,Hay %d camareras.\n"
    "BACK,,menu,Volver\n"
)


def load(tmp_path: Path, text: str) -> Document:
    path = tmp_path / "translations.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return read(path)


def saved(tmp_path: Path, document: Document) -> str:
    path = tmp_path / "out.csv"
    write(document, path)
    return path.read_bytes().decode("utf-8")


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
        ("Jugar", "Play\u3002", "Play"),
        ("Jugar", "Play\u0964", "Play"),
        ("Jugar", "Play\u06d4", "Play"),
        ("Partida guardada.", "Saved\u3002", "Saved\u3002"),
    ],
)
def test_a_final_full_stop_the_source_does_not_have_is_removed(
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


def test_a_document_gets_a_column_with_every_message_translated(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    count = translate_document(backend, document, source="es", target="en")

    assert count == 4
    assert saved(tmp_path, document) == (
        "keys,?plural,?context,es,en\n"
        "?pluralrule,,,nplurals=2; plural=(n != 1);,nplurals=2; plural=(n != 1);\n"
        "PLAY,,,Jugar,English(Jugar)\n"
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,English(Hay %d camarera.)\n"
        ",,,Hay %d camareras.,English(Hay %d camareras.)\n"
        "BACK,,menu,Volver,English(Volver)\n"
    )


def test_each_text_is_described_to_the_model_by_its_row(tmp_path: Path) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="en")

    assert backend.contexts == [
        "translation key PLAY",
        "translation key STAFF; context: female",
        "translation key STAFF; context: female",
        "translation key BACK; context: menu",
    ]


def test_a_plural_form_is_translated_with_a_number_in_place_of_the_count(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="en")

    assert backend.texts[1:3] == ["Hay 1 camarera.", "Hay 2 camareras."]
    assert saved(tmp_path, document).splitlines()[3:5] == [
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,English(Hay %d camarera.)",
        ",,,Hay %d camareras.,English(Hay %d camareras.)",
    ]


def test_a_target_with_more_plural_forms_gets_more_rows(tmp_path: Path) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    count = translate_document(backend, document, source="es", target="ru")

    assert count == 5
    assert backend.texts[1:4] == [
        "Hay 1 camarera.",
        "Hay 2 camareras.",
        "Hay 5 camareras.",
    ]
    assert saved(tmp_path, document).splitlines()[3:6] == [
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,Russian(Hay %d camarera.)",
        ",,,Hay %d camareras.,Russian(Hay %d camareras.)",
        ",,,,Russian(Hay %d camareras.)",
    ]


@pytest.mark.parametrize(
    "reply",
    ["There is one waitress.", "There is 1 waitress, 1 in total.", "No waitress."],
)
def test_a_form_whose_number_does_not_come_back_once_is_described_instead(
    reply: str, tmp_path: Path
) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend({"Hay 1 camarera.": reply})

    translate_document(backend, document, source="es", target="en")

    assert backend.texts[1:3] == ["Hay 1 camarera.", "Hay %d camarera."]
    assert backend.contexts[2] == (
        "translation key STAFF; context: female; plural form: singular, %d is exactly 1"
    )
    assert saved(tmp_path, document).splitlines()[3] == (
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,English(Hay %d camarera.)"
    )


@pytest.mark.parametrize("text", ["Hay camareras.", "Hay %d de %d camareras."])
def test_a_plural_without_exactly_one_count_is_described_to_the_model(
    text: str, tmp_path: Path
) -> None:
    document = load(
        tmp_path, f"keys,?plural,es\nSTAFF,STAFF_PLURAL,Una camarera.\n,,{text}\n"
    )
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="en")

    assert backend.texts == ["Una camarera.", text]
    assert backend.contexts == [
        "translation key STAFF; plural form: singular, %d is exactly 1",
        "translation key STAFF; plural form: plural, %d is a number such as 2, 3 or 4",
    ]


def test_a_target_with_one_plural_form_fills_only_the_first_row(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    count = translate_document(backend, document, source="es", target="ja")

    assert count == 3
    assert saved(tmp_path, document).splitlines()[3:5] == [
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,Japanese(Hay %d camarera.)",
        ",,,Hay %d camareras.,",
    ]


def test_each_plural_form_comes_from_the_source_text_for_its_number(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="ar")

    assert backend.texts[1:7] == [
        "Hay 0 camareras.",
        "Hay 1 camarera.",
        "Hay 2 camareras.",
        "Hay 3 camareras.",
        "Hay 11 camareras.",
        "Hay 100 camareras.",
    ]
    assert [
        line.rsplit(",", 1)[1] for line in saved(tmp_path, document).splitlines()[3:9]
    ] == [
        "Arabic(Hay %d camareras.)",
        "Arabic(Hay %d camarera.)",
        "Arabic(Hay %d camareras.)",
        "Arabic(Hay %d camareras.)",
        "Arabic(Hay %d camareras.)",
        "Arabic(Hay %d camareras.)",
    ]


def test_plural_rows_follow_the_order_of_the_target_rule(tmp_path: Path) -> None:
    # Godot's rule for Hindi puts the form for 1 second.
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="hi")

    assert backend.texts[1:3] == ["Hay 2 camareras.", "Hay 1 camarera."]
    assert saved(tmp_path, document).splitlines()[3:5] == [
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,Hindi(Hay %d camareras.)",
        ",,,Hay %d camareras.,Hindi(Hay %d camarera.)",
    ]


def test_the_source_text_for_a_number_follows_the_source_rule(tmp_path: Path) -> None:
    document = load(
        tmp_path,
        "keys,?plural,hi\nCOINS,COINS_PLURAL,%d many\n,,%d single\n",
    )
    backend = EchoBackend()

    translate_document(backend, document, source="hi", target="en")

    assert backend.texts == ["1 single", "2 many"]


def test_a_number_written_in_the_digits_of_another_script_is_recognised(
    tmp_path: Path,
) -> None:
    # U+0663 is the Arabic-Indic digit three.
    document = load(tmp_path, PLURALS)
    backend = EchoBackend({"Hay 3 camareras.": "Arabic(\u0663 camareras)"})

    translate_document(backend, document, source="es", target="ar")

    fourth_form = saved(tmp_path, document).splitlines()[6]
    assert fourth_form.rsplit(",", 1)[1] == "Arabic(%d camareras)"
    assert "Hay %d camareras." not in backend.texts


def test_a_second_language_reuses_the_rows_the_first_one_added(tmp_path: Path) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()

    translate_document(backend, document, source="es", target="ru")
    translate_document(backend, document, source="es", target="fr")

    assert saved(tmp_path, document).splitlines()[3:6] == [
        "STAFF,STAFF_PLURAL,female,Hay %d camarera.,"
        "Russian(Hay %d camarera.),French(Hay %d camarera.)",
        ",,,Hay %d camareras.,Russian(Hay %d camareras.),French(Hay %d camareras.)",
        ",,,,Russian(Hay %d camareras.),",
    ]


def test_norwegian_goes_to_the_column_godot_names_nb(tmp_path: Path) -> None:
    document = load(tmp_path, "keys,es\nPLAY,Jugar\n")

    translate_document(EchoBackend(), document, source="es", target="no")

    assert saved(tmp_path, document) == ("keys,es,nb\nPLAY,Jugar,Norwegian(Jugar)\n")


def test_a_norwegian_column_already_headed_no_is_reused(tmp_path: Path) -> None:
    document = load(tmp_path, "keys,es,no\nPLAY,Jugar,\n")

    translate_document(EchoBackend(), document, source="es", target="no")

    assert saved(tmp_path, document) == ("keys,es,no\nPLAY,Jugar,Norwegian(Jugar)\n")


def test_norwegian_as_the_source_is_read_from_the_nb_column(tmp_path: Path) -> None:
    document = load(tmp_path, "keys,nb\nPLAY,Spill\n")

    translate_document(EchoBackend(), document, source="no", target="en")

    assert saved(tmp_path, document) == "keys,nb,en\nPLAY,Spill,English(Spill)\n"


def test_messages_already_translated_are_left_alone(tmp_path: Path) -> None:
    document = load(tmp_path, "keys,es,en\nPLAY,Jugar,Play\nQUIT,Salir,\nEMPTY,,\n")
    backend = EchoBackend()

    count = translate_document(backend, document, source="es", target="en")

    assert count == 1
    assert saved(tmp_path, document) == (
        "keys,es,en\nPLAY,Jugar,Play\nQUIT,Salir,English(Salir)\nEMPTY,,\n"
    )


def test_translating_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    document = load(tmp_path, PLURALS)
    backend = EchoBackend()
    translate_document(backend, document, source="es", target="ru")
    first = saved(tmp_path, document)

    count = translate_document(backend, document, source="es", target="ru")

    assert count == 0
    assert saved(tmp_path, document) == first


def test_progress_is_reported_after_each_text(tmp_path: Path) -> None:
    document = load(tmp_path, PLURALS)
    seen: list[tuple[int, int]] = []

    translate_document(
        EchoBackend(),
        document,
        source="es",
        target="en",
        progress=lambda done, total: seen.append((done, total)),
    )

    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_a_missing_source_column_is_reported(tmp_path: Path) -> None:
    document = load(tmp_path, "keys,es\nPLAY,Jugar\n")

    with pytest.raises(MissingLocaleError, match="'fr'"):
        translate_document(EchoBackend(), document, source="fr", target="en")

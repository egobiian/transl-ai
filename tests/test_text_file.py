from collections.abc import Sequence
from pathlib import Path

from transl_ai.prompts import Message
from transl_ai.text_file import output_path, read, translate_text, write


class EchoBackend:
    """Replies with the target language around the text, as `English(Hola)`."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.systems: list[str] = []

    def complete(self, messages: Sequence[Message]) -> str:
        system, user = messages
        self.systems.append(system["content"])
        instructions, text = user["content"].split("\n\n\n", 1)
        self.texts.append(text)
        target = instructions.rsplit(" into ", 1)[1].rstrip(":")
        return f"{target}({text})"


def test_each_paragraph_is_translated_and_the_layout_is_kept() -> None:
    backend = EchoBackend()
    text = "Título\n\nPrimera línea,\nsegunda línea.\n\n\n  Con sangría.  \n"

    translated, count = translate_text(backend, text, source="es", target="en")

    assert backend.texts == ["Título", "Primera línea,\nsegunda línea.", "Con sangría."]
    assert count == 3
    assert translated == (
        "English(Título)\n\n"
        "English(Primera línea,\nsegunda línea.)\n\n\n"
        "  English(Con sangría.)  \n"
    )


def test_paragraphs_go_to_the_model_without_a_row_context() -> None:
    backend = EchoBackend()

    translate_text(backend, "Hola", source="es", target="en")

    assert "Context to pick the right meaning" not in backend.systems[0]


def test_windows_line_endings_are_kept() -> None:
    backend = EchoBackend()

    translated, _ = translate_text(
        backend, "Uno,\r\ndos.\r\n\r\nTres.\r\n", source="es", target="en"
    )

    assert backend.texts == ["Uno,\ndos.", "Tres."]
    assert translated == "English(Uno,\r\ndos.)\r\n\r\nEnglish(Tres.)\r\n"


def test_a_text_with_nothing_to_translate_comes_back_as_it_is() -> None:
    backend = EchoBackend()

    assert translate_text(backend, "\n \n\n", source="es", target="en") == (
        "\n \n\n",
        0,
    )
    assert backend.texts == []


def test_progress_is_reported_after_each_paragraph() -> None:
    seen: list[tuple[int, int]] = []

    translate_text(
        EchoBackend(),
        "Uno.\n\nDos.\n",
        source="es",
        target="en",
        progress=lambda done, total: seen.append((done, total)),
    )

    assert seen == [(1, 2), (2, 2)]


def test_the_translation_of_a_file_is_named_after_the_language() -> None:
    assert output_path(Path("docs/story.txt"), "en") == Path("docs/story.en.txt")
    assert output_path(Path("README"), "fr") == Path("README.fr")


def test_a_file_is_read_and_written_as_utf8_with_its_line_endings(
    tmp_path: Path,
) -> None:
    path = tmp_path / "story.txt"
    path.write_bytes("﻿Camión,\r\naño.\r\n".encode())

    text = read(path)
    write(tmp_path / "copy.txt", text)

    assert text == "Camión,\r\naño.\r\n"
    assert (tmp_path / "copy.txt").read_bytes() == "Camión,\r\naño.\r\n".encode()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["copy.txt", "story.txt"]

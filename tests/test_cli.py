import os
from collections.abc import Sequence
from pathlib import Path

import pytest

from transl_ai import cli
from transl_ai.backends import BackendError
from transl_ai.cli import main
from transl_ai.prompts import Message

SOURCE = (
    "keys,?plural,es,_notes\n"
    "PLAY,,Jugar,\n"
    "COINS,COINS_PLURAL,%d moneda,\n"
    ",,%d monedas,\n"
)


class EchoBackend:
    """Replies with the target language around the text, as `English(Jugar)`."""

    def complete(self, messages: Sequence[Message]) -> str:
        instructions, text = messages[-1]["content"].split("\n\n\n", 1)
        target = instructions.rsplit(" into ", 1)[1].rstrip(":")
        return f"{target}({text})"


class FailingBackend:
    def complete(self, messages: Sequence[Message]) -> str:
        raise BackendError("cannot reach Ollama: start it and try again")


def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "translations.csv"
    path.write_text(SOURCE, encoding="utf-8", newline="")
    return path


def test_version_flag_prints_the_version_and_exits_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("transl-ai ")


def test_the_file_is_updated_with_a_column_per_target_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = source_file(tmp_path)

    code = main([str(path), "--from", "es", "--to", "en", "ru"], EchoBackend())

    assert code == 0
    assert path.read_bytes().decode("utf-8") == (
        "keys,?plural,es,en,ru,_notes\n"
        "PLAY,,Jugar,English(Jugar),Russian(Jugar),\n"
        "COINS,COINS_PLURAL,%d moneda,English(%d moneda),Russian(%d moneda),\n"
        ",,%d monedas,English(%d monedas),Russian(%d monedas),\n"
        ",,,,Russian(%d monedas),\n"
    )
    assert capsys.readouterr().out.splitlines() == [
        f"en: 3 texts translated -> {path}",
        f"ru: 4 texts translated -> {path}",
    ]


def test_norwegian_is_asked_for_as_no_and_written_as_nb(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = source_file(tmp_path)

    main([str(path), "--from", "es", "--to", "no"], EchoBackend())

    assert path.read_bytes().decode("utf-8").splitlines()[:2] == [
        "keys,?plural,es,nb,_notes",
        "PLAY,,Jugar,Norwegian(Jugar),",
    ]
    assert capsys.readouterr().out == f"no: 3 texts translated -> {path}\n"


def test_output_option_writes_elsewhere_and_leaves_the_file_alone(
    tmp_path: Path,
) -> None:
    path = source_file(tmp_path)
    output = tmp_path / "translated.csv"

    main([str(path), "--from", "es", "--to", "en", "-o", str(output)], EchoBackend())

    assert path.read_bytes().decode("utf-8") == SOURCE
    assert output.read_bytes().decode("utf-8").splitlines()[1] == (
        "PLAY,,Jugar,English(Jugar),"
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["missing.csv", "--from", "es", "--to", "en"], "no such file"),
        (["translations.csv", "--from", "fr", "--to", "en"], "has no 'fr' column"),
        (["translations.csv", "--from", "es", "--to", "es"], "repeats the source"),
        (["translations.csv", "--from", "es", "--to", "xx"], "invalid choice"),
    ],
)
def test_a_request_that_cannot_run_is_refused_with_a_reason(
    arguments: list[str],
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        main(arguments, EchoBackend())

    assert excinfo.value.code == 2
    assert message in capsys.readouterr().err
    assert (tmp_path / "translations.csv").read_bytes().decode("utf-8") == SOURCE


def test_a_text_file_gets_a_translated_copy_per_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "story.txt"
    path.write_text("Título\n\nHabía una vez.\n", encoding="utf-8")

    code = main([str(path), "--from", "es", "--to", "en", "fr"], EchoBackend())

    assert code == 0
    assert path.read_text(encoding="utf-8") == "Título\n\nHabía una vez.\n"
    assert (tmp_path / "story.en.txt").read_text(encoding="utf-8") == (
        "English(Título)\n\nEnglish(Había una vez.)\n"
    )
    assert (tmp_path / "story.fr.txt").read_text(encoding="utf-8") == (
        "French(Título)\n\nFrench(Había una vez.)\n"
    )
    assert capsys.readouterr().out.splitlines() == [
        f"en: 2 paragraphs translated -> {tmp_path / 'story.en.txt'}",
        f"fr: 2 paragraphs translated -> {tmp_path / 'story.fr.txt'}",
    ]


def test_a_text_translation_that_exists_is_left_as_it_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "story.txt"
    path.write_text("Hola.\n", encoding="utf-8")
    existing = tmp_path / "story.en.txt"
    existing.write_text("Hello, corrected by hand.\n", encoding="utf-8")

    code = main([str(path), "--from", "es", "--to", "en"], EchoBackend())

    assert code == 0
    assert existing.read_text(encoding="utf-8") == "Hello, corrected by hand.\n"
    assert "already exists, left as it is" in capsys.readouterr().out


def test_output_option_names_the_translation_of_a_text_file(tmp_path: Path) -> None:
    path = tmp_path / "story.txt"
    path.write_text("Hola.\n", encoding="utf-8")
    output = tmp_path / "english.txt"

    main([str(path), "--from", "es", "--to", "en", "-o", str(output)], EchoBackend())

    assert output.read_text(encoding="utf-8") == "English(Hola.)\n"
    assert not (tmp_path / "story.en.txt").exists()


def test_output_option_is_refused_with_several_languages_for_a_text_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "story.txt"
    path.write_text("Hola.\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(
            [str(path), "--from", "es", "--to", "en", "fr", "-o", "out.txt"],
            EchoBackend(),
        )

    assert excinfo.value.code == 2
    assert "-o names one file" in capsys.readouterr().err


def test_a_backend_failure_ends_with_a_message_and_leaves_the_file_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = source_file(tmp_path)

    code = main([str(path), "--from", "es", "--to", "en"], FailingBackend())

    assert code == 1
    assert capsys.readouterr().err == (
        "transl-ai: error: cannot reach Ollama: start it and try again\n"
    )
    assert path.read_bytes().decode("utf-8") == SOURCE


class Recorder:
    """Stands in for the API backends: it keeps how each one was built."""

    def __init__(self) -> None:
        self.built: list[tuple[object, ...]] = []

    def openai(self, model: str, api_key: str | None, base_url: str) -> EchoBackend:
        self.built.append(("openai", model, api_key, base_url))
        return EchoBackend()

    def anthropic(self, model: str) -> EchoBackend:
        self.built.append(("anthropic", model))
        return EchoBackend()


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Recorder:
    """Run from an empty folder, without API keys, and with recorded backends."""
    recorder = Recorder()
    monkeypatch.setattr(cli, "OpenAIBackend", recorder.openai)
    monkeypatch.setattr(cli, "AnthropicBackend", recorder.anthropic)
    kept = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    monkeypatch.setattr(os, "environ", kept)
    monkeypatch.chdir(tmp_path)
    return recorder


def translate(*options: str) -> int:
    path = Path("translations.csv")
    path.write_text(SOURCE, encoding="utf-8", newline="")
    return main([str(path), "--from", "es", "--to", "en", *options])


def test_openai_gets_its_key_from_the_env_file(providers: Recorder) -> None:
    Path(".env").write_text("OPENAI_API_KEY=from-the-file\n", encoding="utf-8")

    assert translate("--provider", "openai", "--model", "some-model") == 0

    assert providers.built == [
        ("openai", "some-model", "from-the-file", "https://api.openai.com/v1")
    ]
    assert "English(Jugar)" in Path("translations.csv").read_text(encoding="utf-8")


def test_a_key_in_the_environment_wins_over_the_env_file(
    providers: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    Path(".env").write_text("OPENAI_API_KEY=from-the-file\n", encoding="utf-8")
    monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "from-the-shell")

    translate("--provider", "openai", "--model", "some-model")

    assert providers.built[0][2] == "from-the-shell"


def test_api_base_points_openai_at_a_compatible_api(providers: Recorder) -> None:
    translate("--api-base", "http://localhost:1234/v1", "--model", "some-model")

    assert providers.built == [
        ("openai", "some-model", None, "http://localhost:1234/v1")
    ]


@pytest.mark.parametrize(
    ("options", "model"),
    [
        (["--provider", "anthropic"], "claude-opus-5-5"),
        (
            ["--provider", "anthropic", "--model", "claude-haiku-5-5"],
            "claude-haiku-5-5",
        ),
    ],
)
def test_anthropic_uses_the_model_asked_for_or_its_default(
    options: list[str], model: str, providers: Recorder
) -> None:
    assert translate(*options) == 0

    assert providers.built == [("anthropic", model)]


def test_ollama_stays_the_provider_when_none_is_named(providers: Recorder) -> None:
    path = Path("translations.csv")
    path.write_text(SOURCE, encoding="utf-8", newline="")

    main([str(path), "--from", "es", "--to", "en"], EchoBackend())

    assert providers.built == []


def test_openai_without_a_key_ends_with_where_to_put_it(
    providers: Recorder, capsys: pytest.CaptureFixture[str]
) -> None:
    code = translate("--provider", "openai", "--model", "some-model")

    assert code == 1
    assert capsys.readouterr().err == (
        "transl-ai: error: no OpenAI key: put OPENAI_API_KEY in a .env file or in"
        " the environment\n"
    )
    assert providers.built == []
    assert Path("translations.csv").read_text(encoding="utf-8") == SOURCE


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--provider", "openai"], "--provider openai needs --model"),
        (
            ["--provider", "anthropic", "--api-base", "https://api.example.com/v1"],
            "--api-base goes with --provider openai",
        ),
        (["--api-base", "file:///etc/passwd", "--model", "m"], "not an http"),
        (["--provider", "other"], "invalid choice"),
    ],
)
def test_a_provider_request_that_cannot_run_is_refused_with_a_reason(
    options: list[str],
    message: str,
    providers: Recorder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        translate(*options)

    assert excinfo.value.code == 2
    assert message in capsys.readouterr().err
    assert providers.built == []

from collections.abc import Sequence
from pathlib import Path

import pytest

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

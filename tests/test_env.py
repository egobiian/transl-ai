from pathlib import Path

from transl_ai.env import load_env_file


def load(
    tmp_path: Path, text: str, environ: dict[str, str] | None = None
) -> dict[str, str]:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    target = {} if environ is None else environ
    load_env_file(path, target)
    return target


def test_each_assignment_becomes_a_variable(tmp_path: Path) -> None:
    text = "OPENAI_API_KEY=sk-one\nANTHROPIC_API_KEY = sk-two \n"

    assert load(tmp_path, text) == {
        "OPENAI_API_KEY": "sk-one",
        "ANTHROPIC_API_KEY": "sk-two",
    }


def test_comments_blank_lines_and_other_text_are_ignored(tmp_path: Path) -> None:
    text = "# OPENAI_API_KEY=commented\n\nnot an assignment\n=no name\nKEY=value\n"

    assert load(tmp_path, text) == {"KEY": "value"}


def test_quotes_and_an_export_prefix_are_accepted(tmp_path: Path) -> None:
    text = "export A=\"one two\"\nB='three'\nC=four=five\n"

    assert load(tmp_path, text) == {"A": "one two", "B": "three", "C": "four=five"}


def test_an_empty_value_is_not_set(tmp_path: Path) -> None:
    assert load(tmp_path, 'OPENAI_API_KEY=\nANTHROPIC_API_KEY=""\n') == {}


def test_a_variable_that_is_already_set_wins(tmp_path: Path) -> None:
    environ = {"OPENAI_API_KEY": "from the shell"}

    load(tmp_path, "OPENAI_API_KEY=from the file\n", environ)

    assert environ == {"OPENAI_API_KEY": "from the shell"}


def test_a_file_that_is_not_there_changes_nothing(tmp_path: Path) -> None:
    environ = {"KEPT": "yes"}

    load_env_file(tmp_path / "missing.env", environ)

    assert environ == {"KEPT": "yes"}

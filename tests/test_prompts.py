import pytest

from transl_ai.prompts import UnknownLanguageError, build_context, build_messages


def test_user_message_is_the_documented_translategemma_prompt() -> None:
    _, user = build_messages("Jugar", source="es", target="en")

    assert user == {
        "role": "user",
        "content": (
            "You are a professional Spanish (es) to English (en) translator. Your"
            " goal is to accurately convey the meaning and nuances of the original"
            " Spanish text while adhering to English grammar, vocabulary, and"
            " cultural sensitivities.\n"
            "Produce only the English translation, without any additional"
            " explanations or commentary. Please translate the following Spanish"
            " text into English:\n\n\nJugar"
        ),
    }


def test_system_message_carries_the_rules_and_no_context_line_by_default() -> None:
    system, _ = build_messages("Jugar", source="es", target="en")

    assert system["role"] == "system"
    assert "Keep the grammatical number of the source" in system["content"]
    assert "Context to pick the right meaning" not in system["content"]


def test_every_rule_with_examples_shows_a_good_and_a_bad_one() -> None:
    system, _ = build_messages("Jugar", source="es", target="en")

    lines = system["content"].splitlines()
    assert sum(line.lstrip().startswith("GOOD:") for line in lines) == 3
    assert sum(line.lstrip().startswith("BAD:") for line in lines) == 3


def test_context_goes_in_the_system_message_only() -> None:
    system, user = build_messages(
        "Salir", source="es", target="fr", context="translation key MENU_QUIT"
    )

    assert system["content"].endswith(
        "Context to pick the right meaning (do not translate it or mention it):"
        " translation key MENU_QUIT\n"
    )
    assert "MENU_QUIT" not in user["content"]


def test_braces_in_the_text_and_the_context_are_kept_literally() -> None:
    system, user = build_messages(
        "Has encontrado [b]{item}[/b].",
        source="es",
        target="de",
        context="the {item} placeholder is kept",
    )

    assert user["content"].endswith("\n\n\nHas encontrado [b]{item}[/b].")
    assert "the {item} placeholder is kept" in system["content"]


def test_context_of_a_plain_row_is_its_key() -> None:
    assert build_context("MENU_QUIT") == "translation key MENU_QUIT"


def test_context_includes_the_context_column() -> None:
    assert (
        build_context("BACK", context="menu") == "translation key BACK; context: menu"
    )


@pytest.mark.parametrize(
    ("plural_form", "hint"),
    [
        (0, "plural form: singular, %d is exactly 1"),
        (1, "plural form: plural, %d is 2 or more"),
        (2, "plural form: plural, %d is 2 or more"),
    ],
)
def test_context_says_which_plural_form_the_row_is(plural_form: int, hint: str) -> None:
    described = build_context("STAFF", context="female", plural_form=plural_form)

    assert described == f"translation key STAFF; context: female; {hint}"


def test_unknown_language_code_is_rejected() -> None:
    with pytest.raises(UnknownLanguageError, match="'xx'"):
        build_messages("Jugar", source="es", target="xx")

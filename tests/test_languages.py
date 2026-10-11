import pytest

from transl_ai.languages import LANGUAGES, UnknownLanguageError, language

# The 55 WMT24++ pairs of the TranslateGemma report, without their regions, and
# English, which every pair has on the other side.
EVALUATED = (
    "ar bg bn ca cs da de el en es et fa fi fil fr gu he hi hr hu id is it ja kn ko"
    " lt lv ml mr nl no pa pl pt ro ru sk sl sr sv sw ta te th tr uk ur vi zh zu"
)
EU_OFFICIAL = "bg cs da de el en es et fi fr ga hr hu it lt lv mt nl pl pt ro sk sl sv"


def test_the_languages_are_the_evaluated_ones_and_the_official_eu_ones() -> None:
    assert set(LANGUAGES) == set(EVALUATED.split()) | set(EU_OFFICIAL.split())
    assert len(LANGUAGES) == 53


def test_no_language_is_a_regional_locale() -> None:
    assert [code for code in LANGUAGES if not code.isalpha()] == []


@pytest.mark.parametrize("code", sorted(LANGUAGES))
def test_every_number_takes_one_of_the_plural_forms(code: str) -> None:
    known = language(code)
    count = len(known.plural_forms)

    assert {known.form_of(number) for number in range(1001)} <= set(range(count))


@pytest.mark.parametrize("code", sorted(LANGUAGES))
def test_each_plural_form_is_shown_with_a_number_that_takes_it(code: str) -> None:
    known = language(code)

    assert [known.form_of(form.number) for form in known.plural_forms] == list(
        range(len(known.plural_forms))
    )


@pytest.mark.parametrize("code", sorted(LANGUAGES))
def test_one_is_the_number_of_the_form_a_single_item_takes(code: str) -> None:
    known = language(code)

    single = known.plural_forms[known.form_of(1)]

    assert single.number == 1
    assert single.hint == "singular, %d is exactly 1"


@pytest.mark.parametrize(
    ("code", "numbers"),
    [
        ("ja", [1]),
        ("es", [1, 2]),
        ("fr", [1, 2]),
        ("hi", [2, 1]),
        ("ru", [1, 2, 5]),
        ("pl", [1, 2, 5]),
        ("lt", [1, 2, 10]),
        ("lv", [1, 2, 0]),
        ("sl", [1, 2, 3, 5]),
        ("ar", [0, 1, 2, 3, 11, 100]),
    ],
)
def test_plural_forms_follow_the_order_of_the_rule(
    code: str, numbers: list[int]
) -> None:
    assert [form.number for form in language(code).plural_forms] == numbers


def test_a_plural_form_is_described_by_the_numbers_that_take_it() -> None:
    assert [form.hint for form in language("ar").plural_forms] == [
        "plural, %d is exactly 0",
        "singular, %d is exactly 1",
        "plural, %d is exactly 2",
        "plural, %d is a number such as 3, 4 or 5",
        "plural, %d is a number such as 11, 12 or 13",
        "plural, %d is a number such as 100, 101 or 102",
    ]


def test_unknown_language_code_is_rejected() -> None:
    with pytest.raises(UnknownLanguageError, match="'xx'"):
        language("xx")

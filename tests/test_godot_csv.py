from pathlib import Path

import pytest

from transl_ai.godot_csv import Entry, MissingLocaleError, entries, read_rows


def test_read_rows_parses_quoted_commas_quotes_and_line_breaks(tmp_path: Path) -> None:
    path = tmp_path / "translations.csv"
    path.write_text(
        'keys,es\nGREETING,"Hola, %s"\nQUOTE,"""Sí"", dijo."\nINTRO,"Uno,\ndos"\n',
        encoding="utf-8",
    )

    assert read_rows(path) == [
        ["keys", "es"],
        ["GREETING", "Hola, %s"],
        ["QUOTE", '"Sí", dijo.'],
        ["INTRO", "Uno,\ndos"],
    ]


def test_read_rows_tolerates_a_byte_order_mark(tmp_path: Path) -> None:
    path = tmp_path / "translations.csv"
    path.write_bytes(b"\xef\xbb\xbfkeys,es\nPLAY,Jugar\n")

    assert read_rows(path)[0] == ["keys", "es"]


def test_entries_carry_key_text_context_and_notes() -> None:
    rows = [
        ["keys", "?context", "es", "_notes"],
        ["PLAY", "", "Jugar", ""],
        ["BACK", "menu", "Volver", "The menu button."],
    ]

    assert entries(rows, "es") == [
        Entry(row=1, key="PLAY", text="Jugar"),
        Entry(
            row=2, key="BACK", text="Volver", context="menu", notes="The menu button."
        ),
    ]


def test_special_columns_are_found_in_any_position_and_letter_case() -> None:
    rows = [
        ["", "es", "?Context", "_a", "_b"],
        ["BACK", "Volver", "menu", "First.", "Second."],
    ]

    assert entries(rows, "es") == [
        Entry(row=1, key="BACK", text="Volver", context="menu", notes="First. Second.")
    ]


def test_plural_rows_share_the_key_and_context_and_are_numbered() -> None:
    rows = [
        ["keys", "?plural", "?context", "es"],
        ["STAFF", "STAFF_PLURAL", "female", "Hay %d camarera."],
        ["", "", "", "Hay %d camareras."],
        ["PLAY", "", "", "Jugar"],
    ]

    assert entries(rows, "es") == [
        Entry(
            row=1, key="STAFF", text="Hay %d camarera.", context="female", plural_form=0
        ),
        Entry(
            row=2,
            key="STAFF",
            text="Hay %d camareras.",
            context="female",
            plural_form=1,
        ),
        Entry(row=3, key="PLAY", text="Jugar"),
    ]


def test_a_new_plural_block_ends_the_previous_one() -> None:
    rows = [
        ["keys", "?plural", "es"],
        ["COINS", "COINS_PLURAL", "%d moneda"],
        ["", "", "%d monedas"],
        ["GEMS", "GEMS_PLURAL", "%d gema"],
        ["", "", "%d gemas"],
    ]

    assert [(e.key, e.plural_form) for e in entries(rows, "es")] == [
        ("COINS", 0),
        ("COINS", 1),
        ("GEMS", 0),
        ("GEMS", 1),
    ]


def test_rows_godot_skips_are_not_entries() -> None:
    rows = [
        ["keys", "?plural", "es", "_notes"],
        ["", "optional", "required", "A legend row: its key is empty."],
        ["?pluralrule", "", "nplurals=2; plural=(n != 1);", ""],
        [],
        ["", "", "", ""],
        ["EMPTY", "", "", "Nothing to translate."],
        ["PLAY", "", "Jugar", ""],
    ]

    assert entries(rows, "es") == [Entry(row=6, key="PLAY", text="Jugar")]


def test_short_rows_are_read_as_if_padded_with_empty_cells() -> None:
    rows = [["keys", "es", "?context", "_notes"], ["PLAY", "Jugar"]]

    assert entries(rows, "es") == [Entry(row=1, key="PLAY", text="Jugar")]


def test_a_missing_locale_column_is_reported() -> None:
    with pytest.raises(MissingLocaleError, match="'fr'"):
        entries([["keys", "es"], ["PLAY", "Jugar"]], "fr")


def test_an_empty_file_is_reported() -> None:
    with pytest.raises(MissingLocaleError, match="empty"):
        entries([], "es")

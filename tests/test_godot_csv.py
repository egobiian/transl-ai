from pathlib import Path

from transl_ai.godot_csv import Document, read, write

SAMPLE = (
    "keys,?plural,?context,es,_notes\n"
    ",optional,optional,required,A legend row.\n"
    "?pluralrule,,,nplurals=2; plural=(n != 1);,\n"
    "PLAY,,,Jugar,\n"
    'GREETING,,female,"Hola, %s",Has a comma.\n'
    "COINS,COINS_PLURAL,,%d moneda,\n"
    ",,,%d monedas,\n"
    "BACK,,menu,Volver,\n"
)


def load(tmp_path: Path, text: str) -> Document:
    path = tmp_path / "translations.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return read(path)


def saved(tmp_path: Path, document: Document) -> str:
    path = tmp_path / "out.csv"
    write(document, path)
    return path.read_bytes().decode("utf-8")


def test_messages_carry_key_context_and_whether_they_are_plural(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, SAMPLE)

    assert [(m.key, m.context, m.plural) for m in document.messages()] == [
        ("PLAY", "", False),
        ("GREETING", "female", False),
        ("COINS", "", True),
        ("BACK", "menu", False),
    ]


def test_forms_are_the_non_empty_texts_of_a_column(tmp_path: Path) -> None:
    document = load(tmp_path, SAMPLE)
    column = document.column("es")
    assert column is not None

    assert [m.forms(column) for m in document.messages()] == [
        ["Jugar"],
        ["Hola, %s"],
        ["%d moneda", "%d monedas"],
        ["Volver"],
    ]


def test_quoted_commas_quotes_and_line_breaks_are_read(tmp_path: Path) -> None:
    document = load(tmp_path, 'keys,es\nQUOTE,"""Sí"", dijo."\nINTRO,"Uno,\ndos"\n')

    assert [m.forms(1) for m in document.messages()] == [
        ['"Sí", dijo.'],
        ["Uno,\ndos"],
    ]


def test_special_columns_are_found_in_any_position_and_letter_case(
    tmp_path: Path,
) -> None:
    document = load(tmp_path, ",es,?Context,?PLURAL\nBACK,Volver,menu,\n")

    assert document.column("es") == 1
    assert [(m.key, m.context) for m in document.messages()] == [("BACK", "menu")]


def test_a_new_key_ends_a_plural_block(tmp_path: Path) -> None:
    document = load(
        tmp_path,
        "keys,?plural,es\n"
        "COINS,COINS_PLURAL,%d moneda\n"
        ",,%d monedas\n"
        "GEMS,GEMS_PLURAL,%d gema\n"
        ",,%d gemas\n",
    )

    assert [(m.key, m.forms(2)) for m in document.messages()] == [
        ("COINS", ["%d moneda", "%d monedas"]),
        ("GEMS", ["%d gema", "%d gemas"]),
    ]


def test_a_skipped_row_inside_a_plural_block_does_not_split_it(tmp_path: Path) -> None:
    document = load(
        tmp_path,
        "keys,?plural,es\n"
        "COINS,COINS_PLURAL,%d moneda\n"
        "?pluralrule,,nplurals=2; plural=(n != 1);\n"
        ",,%d monedas\n",
    )

    (coins,) = document.messages()
    assert coins.forms(2) == ["%d moneda", "%d monedas"]
    assert saved(tmp_path, document) == (
        "keys,?plural,es\n"
        "?pluralrule,,nplurals=2; plural=(n != 1);\n"
        "COINS,COINS_PLURAL,%d moneda\n"
        ",,%d monedas\n"
    )


def test_an_untouched_file_is_written_back_identically(tmp_path: Path) -> None:
    text = SAMPLE + "\nSHORT,,,Corto\n"

    assert saved(tmp_path, load(tmp_path, text)) == text


def test_windows_line_endings_are_kept(tmp_path: Path) -> None:
    text = "keys,es\r\nPLAY,Jugar\r\n"

    assert saved(tmp_path, load(tmp_path, text)) == text


def test_a_byte_order_mark_is_read_and_not_written_back(tmp_path: Path) -> None:
    document = load(tmp_path, "﻿keys,es\nPLAY,Jugar\n")

    assert document.column("es") == 1
    assert saved(tmp_path, document) == "keys,es\nPLAY,Jugar\n"


def test_writing_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    document = load(tmp_path, SAMPLE)

    write(document, tmp_path / "out.csv")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.csv", "translations.csv"]


def test_a_new_locale_goes_after_the_last_locale_column(tmp_path: Path) -> None:
    document = load(tmp_path, SAMPLE + "\nSHORT,,,Corto\n")

    assert document.add_locale("en") == 4

    assert saved(tmp_path, document) == (
        "keys,?plural,?context,es,en,_notes\n"
        ",optional,optional,required,,A legend row.\n"
        "?pluralrule,,,nplurals=2; plural=(n != 1);,,\n"
        "PLAY,,,Jugar,,\n"
        'GREETING,,female,"Hola, %s",,Has a comma.\n'
        "COINS,COINS_PLURAL,,%d moneda,,\n"
        ",,,%d monedas,,\n"
        "BACK,,menu,Volver,,\n"
        "\n"
        "SHORT,,,Corto,\n"
    )


def test_a_form_beyond_the_rows_of_a_plural_block_adds_a_row(tmp_path: Path) -> None:
    document = load(
        tmp_path,
        "keys,?plural,es,ru\n"
        "COINS,COINS_PLURAL,%d moneda,\n"
        ",,%d monedas,\n"
        "PLAY,,Jugar,\n",
    )
    coins, play = document.messages()

    for index, text in enumerate(["%d монета", "%d монеты", "%d монет"]):
        document.set_form(coins, index, 3, text)
    document.set_form(play, 0, 3, "Играть")

    assert saved(tmp_path, document) == (
        "keys,?plural,es,ru\n"
        "COINS,COINS_PLURAL,%d moneda,%d монета\n"
        ",,%d monedas,%d монеты\n"
        ",,,%d монет\n"
        "PLAY,,Jugar,Играть\n"
    )


def test_the_plural_rule_row_gets_the_rule_of_a_new_locale(tmp_path: Path) -> None:
    document = load(tmp_path, SAMPLE)
    english = document.add_locale("en")

    document.declare_plural_rule(english, "nplurals=2; plural=(n != 1);")

    assert (
        "?pluralrule,,,nplurals=2; plural=(n != 1);,nplurals=2; plural=(n != 1);,"
        in (saved(tmp_path, document))
    )


def test_a_declared_plural_rule_is_not_overwritten(tmp_path: Path) -> None:
    text = "keys,?plural,es\n?pluralrule,,custom rule\nCOINS,COINS_PLURAL,%d moneda\n"
    document = load(tmp_path, text)

    document.declare_plural_rule(2, "nplurals=2; plural=(n != 1);")

    assert saved(tmp_path, document) == text


def test_a_file_without_a_plural_rule_row_does_not_get_one(tmp_path: Path) -> None:
    text = "keys,?plural,es\nCOINS,COINS_PLURAL,%d moneda\n"
    document = load(tmp_path, text)

    document.declare_plural_rule(2, "nplurals=2; plural=(n != 1);")

    assert saved(tmp_path, document) == text

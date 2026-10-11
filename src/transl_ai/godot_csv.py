"""Read Godot translation CSV files.

The layout is the one Godot's CSV translation importer accepts: the first column
holds the keys, `?context` and `?plural` are optional special columns, a column
whose header starts with `_` is a comment, and every other column is a locale.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

CONTEXT_COLUMN = "?context"
PLURAL_COLUMN = "?plural"
PLURAL_RULE_KEY = "?pluralrule"
COMMENT_PREFIX = "_"


@dataclass(frozen=True)
class Entry:
    """One text to translate, with what the file says about it."""

    row: int
    key: str
    text: str
    context: str = ""
    plural_form: int | None = None
    notes: str = ""


class MissingLocaleError(ValueError):
    """Raised when the file has no column for the requested locale."""


def read_rows(path: Path, *, delimiter: str = ",") -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle, delimiter=delimiter))


def entries(rows: Sequence[Sequence[str]], locale: str) -> list[Entry]:
    """Return the texts of `locale`, skipping the rows Godot itself skips."""
    if not rows:
        raise MissingLocaleError(f"the file is empty, so it has no {locale!r} column")
    header = rows[0]
    context_column = _find(header, CONTEXT_COLUMN)
    plural_column = _find(header, PLURAL_COLUMN)
    locale_column = _find(header, locale)
    if locale_column is None:
        raise MissingLocaleError(f"the file has no {locale!r} column")
    comment_columns = [
        index
        for index, name in enumerate(header)
        if index > 0 and name.startswith(COMMENT_PREFIX)
    ]

    found: list[Entry] = []
    key = context = ""
    in_plural = False
    forms_seen = 0
    for number, row in enumerate(rows[1:], start=1):
        if not any(row) or row[0].lower() == PLURAL_RULE_KEY:
            continue
        row_key = row[0]
        row_context = _cell(row, context_column)
        row_plural = _cell(row, plural_column)
        # A plural block runs until a row names a key, a context or a plural again.
        if in_plural and (row_key or row_context or row_plural):
            in_plural = False
        if not in_plural:
            if not row_key:
                continue
            key, context = row_key, row_context
            in_plural = bool(row_plural)
            forms_seen = 0
        text = _cell(row, locale_column)
        if not text:
            continue
        found.append(
            Entry(
                row=number,
                key=key,
                text=text,
                context=context,
                plural_form=forms_seen if in_plural else None,
                notes=" ".join(
                    note for index in comment_columns if (note := _cell(row, index))
                ),
            )
        )
        forms_seen += 1
    return found


def _find(header: Sequence[str], name: str) -> int | None:
    # Godot ignores the first header cell and matches the special names in any case.
    special = name.startswith("?")
    for index, cell in enumerate(header):
        if index > 0 and (cell.lower() if special else cell) == name:
            return index
    return None


def _cell(row: Sequence[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""

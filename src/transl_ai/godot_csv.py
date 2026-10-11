"""Read and write Godot translation CSV files.

The layout is the one Godot's CSV translation importer accepts: the first column
holds the keys, `?context` and `?plural` are optional special columns, a column
whose header starts with `_` is a comment, and every other column is a locale.
"""

import csv
import io
from dataclasses import dataclass
from pathlib import Path

CONTEXT_COLUMN = "?context"
PLURAL_COLUMN = "?plural"
PLURAL_RULE_KEY = "?pluralrule"

Row = list[str]


@dataclass
class Block:
    """Rows that belong together: one message, or one row Godot skips."""

    rows: list[Row]
    key: str = ""
    context: str = ""
    plural: bool = False

    def forms(self, column: int) -> list[str]:
        """The texts of a column as Godot reads them: empty cells do not count."""
        return [text for row in self.rows if (text := _cell(row, column))]


@dataclass
class Document:
    header: Row
    blocks: list[Block]
    delimiter: str = ","
    newline: str = "\n"

    def column(self, name: str) -> int | None:
        return _find(self.header, name)

    def messages(self) -> list[Block]:
        return [block for block in self.blocks if block.key]

    def add_locale(self, locale: str) -> int:
        """Add an empty column for `locale` after the last locale and return it."""
        locales = [
            index
            for index, name in enumerate(self.header)
            if index > 0 and not name.startswith(("_", "?"))
        ]
        position = locales[-1] + 1 if locales else len(self.header)
        self.header.insert(position, locale)
        for block in self.blocks:
            for row in block.rows:
                # A shorter row has no cell to push aside: it already reads as empty.
                if len(row) >= position:
                    row.insert(position, "")
        return position

    def set_form(self, block: Block, index: int, column: int, text: str) -> None:
        """Write the `index`-th text of a block, adding plural rows as needed."""
        while len(block.rows) <= index:
            block.rows.append([""] * len(self.header))
        _set(block.rows[index], column, text)

    def declare_plural_rule(self, column: int, rule: str) -> None:
        """Fill a locale's cell of the `?pluralrule` row, when the file has one."""
        rule_rows = [
            block.rows[0]
            for block in self.blocks
            if _cell(block.rows[0], 0).lower() == PLURAL_RULE_KEY
        ]
        if rule_rows and not any(_cell(row, column) for row in rule_rows):
            _set(rule_rows[0], column, rule)


class MissingLocaleError(ValueError):
    """Raised when the file has no column for the requested locale."""


def read(path: Path, *, delimiter: str = ",") -> Document:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    header = rows[0] if rows else []
    return Document(
        header=header,
        blocks=_blocks(header, rows[1:]),
        delimiter=delimiter,
        newline="\r\n" if "\r\n" in text else "\n",
    )


def write(document: Document, path: Path) -> None:
    rows = [document.header]
    rows.extend(row for block in document.blocks for row in block.rows)
    # Written aside and then moved over, so a failure cannot leave half a file.
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(
                handle, delimiter=document.delimiter, lineterminator=document.newline
            )
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _blocks(header: Row, rows: list[Row]) -> list[Block]:
    context_column = _find(header, CONTEXT_COLUMN)
    plural_column = _find(header, PLURAL_COLUMN)
    blocks: list[Block] = []
    open_plural: Block | None = None
    for row in rows:
        key = _cell(row, 0)
        if not any(row) or key.lower() == PLURAL_RULE_KEY:
            # Godot reads these wherever they are, so one found inside a plural
            # block goes before it and the block stays whole.
            position = len(blocks) if open_plural is None else len(blocks) - 1
            blocks.insert(position, Block([row]))
            continue
        context = _cell(row, context_column)
        plural = _cell(row, plural_column)
        if open_plural is not None and not (key or context or plural):
            open_plural.rows.append(row)
            continue
        block = Block([row], key=key, context=context, plural=bool(key and plural))
        blocks.append(block)
        open_plural = block if block.plural else None
    return blocks


def _find(header: Row, name: str) -> int | None:
    # Godot ignores the first header cell and matches the special names in any case.
    special = name.startswith("?")
    for index, cell in enumerate(header):
        if index > 0 and (cell.lower() if special else cell) == name:
            return index
    return None


def _cell(row: Row, index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def _set(row: Row, column: int, text: str) -> None:
    row.extend([""] * (column + 1 - len(row)))
    row[column] = text

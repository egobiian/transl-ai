"""Writing files."""

from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """Write `text` as UTF-8, with its line endings as they are.

    It is written aside and then moved over, so a failure cannot leave half a file.
    """
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

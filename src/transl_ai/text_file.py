"""Translate plain text files, one paragraph at a time."""

import re
from pathlib import Path

from transl_ai.backends import Backend
from transl_ai.files import write_text
from transl_ai.translator import Progress, translate

# One or more blank lines, which may hold spaces.
PARAGRAPH_BREAK = re.compile(r"(\n(?:[ \t]*\n)+)")


def read(path: Path) -> str:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def write(path: Path, text: str) -> None:
    write_text(path, text)


def output_path(path: Path, target: str) -> Path:
    """Where the translation of `path` into `target` goes: `story.en.txt`."""
    return path.with_name(f"{path.stem}.{target}{path.suffix}")


def translate_text(
    backend: Backend,
    text: str,
    *,
    source: str,
    target: str,
    progress: Progress | None = None,
) -> tuple[str, int]:
    """Translate the paragraphs of `text`; return it with how many there were.

    Blank lines, indentation and line endings stay as they are.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    pieces = PARAGRAPH_BREAK.split(text.replace("\r\n", "\n"))
    total = sum(bool(piece.strip()) for piece in pieces)
    done = 0
    for index, piece in enumerate(pieces):
        paragraph = piece.strip()
        if not paragraph:
            continue
        before = piece[: len(piece) - len(piece.lstrip())]
        after = piece[len(piece.rstrip()) :]
        translation = translate(backend, paragraph, source=source, target=target)
        pieces[index] = before + translation + after
        done += 1
        if progress is not None:
            progress(done, total)
    return "".join(pieces).replace("\n", newline), done

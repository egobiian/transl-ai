"""Command-line entry point."""

import argparse
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from transl_ai import godot_csv
from transl_ai.backends import Backend, OllamaBackend
from transl_ai.config import DEFAULT_MODEL
from transl_ai.languages import LANGUAGES, language
from transl_ai.translator import Progress, locale_column, translate_document


def build_parser() -> argparse.ArgumentParser:
    languages = sorted(LANGUAGES)
    parser = argparse.ArgumentParser(
        prog="transl-ai",
        description="Translate Godot CSV localization files with Ollama.",
        epilog=(
            f"LANG is one of: {', '.join(languages)}."
            " Norwegian (no) is the nb column in the file, the name Godot gives it."
        ),
    )
    parser.add_argument("file", type=Path, help="Godot translation CSV to translate")
    parser.add_argument(
        "--from",
        dest="source",
        required=True,
        choices=languages,
        metavar="LANG",
        help="locale column to translate from",
    )
    parser.add_argument(
        "--to",
        dest="targets",
        required=True,
        nargs="+",
        choices=languages,
        metavar="LANG",
        help="locale columns to fill, added to the file when missing",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="write the result here instead of updating FILE",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="Ollama model (default: %(default)s)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {metadata.version('transl-ai')}",
    )
    return parser


def main(argv: Sequence[str] | None = None, backend: Backend | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.source in args.targets:
        parser.error(f"--to repeats the source language {args.source!r}")
    try:
        document = godot_csv.read(args.file)
    except FileNotFoundError:
        parser.error(f"no such file: {args.file}")
    if locale_column(document, args.source) is None:
        parser.error(f"{args.file} has no {language(args.source).locale!r} column")

    if backend is None:
        backend = OllamaBackend(model=args.model)
    output: Path = args.output or args.file
    for target in args.targets:
        count = translate_document(
            backend,
            document,
            source=args.source,
            target=target,
            progress=_progress(target),
        )
        # Saved after each language, so an interrupted run keeps the finished ones.
        godot_csv.write(document, output)
        print(f"{target}: {count} texts translated -> {output}")
    return 0


def _progress(target: str) -> Progress | None:
    if not sys.stderr.isatty():
        return None

    def show(done: int, total: int) -> None:
        end = "\n" if done == total else ""
        print(f"\r{target}: {done}/{total}", end=end, file=sys.stderr, flush=True)

    return show

"""Command-line entry point."""

import argparse
import os
import sys
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from transl_ai import godot_csv, text_file
from transl_ai.backends import (
    AnthropicBackend,
    Backend,
    BackendError,
    OllamaBackend,
    OpenAIBackend,
)
from transl_ai.config import (
    ANTHROPIC_KEY_VARIABLE,
    ANTHROPIC_MODEL,
    ENV_FILE,
    OLLAMA_MODEL,
    OPENAI_API,
    OPENAI_KEY_VARIABLE,
)
from transl_ai.env import load_env_file
from transl_ai.languages import LANGUAGES, language
from transl_ai.translator import Progress, locale_column, translate_document

PROVIDERS = ("ollama", "openai", "anthropic")


def build_parser() -> argparse.ArgumentParser:
    languages = sorted(LANGUAGES)
    parser = argparse.ArgumentParser(
        prog="transl-ai",
        description=(
            "Translate a Godot CSV localization file, or a plain text file, with a"
            " model served by Ollama, OpenAI or Anthropic."
        ),
        epilog=(
            f"LANG is one of: {', '.join(languages)}."
            " Norwegian (no) is the nb column in a CSV, the name Godot gives it."
            f" The API keys are read from {OPENAI_KEY_VARIABLE} and"
            f" {ANTHROPIC_KEY_VARIABLE}, in the environment or in a {ENV_FILE} file"
            " in the folder the command runs from."
        ),
    )
    parser.add_argument(
        "file",
        type=Path,
        help="a .csv is read as a Godot translation CSV, anything else as plain text",
    )
    parser.add_argument(
        "--from",
        dest="source",
        required=True,
        choices=languages,
        metavar="LANG",
        help="language to translate from: its column in a CSV",
    )
    parser.add_argument(
        "--to",
        dest="targets",
        required=True,
        nargs="+",
        choices=languages,
        metavar="LANG",
        help=(
            "languages to translate into: a CSV gets a column for each, a text file"
            " a copy for each, such as story.en.txt"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "write the result here: by default a CSV is updated in place and a text"
            " file is written next to FILE"
        ),
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        help="who serves the model (default: ollama)",
    )
    parser.add_argument(
        "--model",
        help=(
            f"model to use (default: {OLLAMA_MODEL} with ollama, {ANTHROPIC_MODEL}"
            " with anthropic; openai needs one)"
        ),
    )
    parser.add_argument(
        "--api-base",
        type=_api_address,
        metavar="URL",
        help=(
            "with openai, the address of another API that speaks its chat"
            f" completions format (default: {OPENAI_API})"
        ),
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
    if not args.file.is_file():
        parser.error(f"no such file: {args.file}")
    load_env_file(Path(ENV_FILE))
    try:
        if backend is None:
            backend = _backend(parser, args)
        if args.file.suffix.lower() == ".csv":
            _translate_csv(parser, args, backend)
        else:
            _translate_text(parser, args, backend)
    except BackendError as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 1
    return 0


def _backend(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Backend:
    provider = args.provider or ("openai" if args.api_base else "ollama")
    if provider != "openai" and args.api_base is not None:
        parser.error("--api-base goes with --provider openai")
    if provider == "ollama":
        return OllamaBackend(model=args.model or OLLAMA_MODEL)
    if provider == "anthropic":
        return AnthropicBackend(model=args.model or ANTHROPIC_MODEL)
    if args.model is None:
        parser.error("--provider openai needs --model, the name of the model to use")
    key = os.environ.get(OPENAI_KEY_VARIABLE)
    if key is None and args.api_base is None:
        raise BackendError(
            f"no OpenAI key: put {OPENAI_KEY_VARIABLE} in a {ENV_FILE} file or in"
            " the environment"
        )
    return OpenAIBackend(args.model, key, args.api_base or OPENAI_API)


def _translate_csv(
    parser: argparse.ArgumentParser, args: argparse.Namespace, backend: Backend
) -> None:
    document = godot_csv.read(args.file)
    if locale_column(document, args.source) is None:
        parser.error(f"{args.file} has no {language(args.source).locale!r} column")
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


def _translate_text(
    parser: argparse.ArgumentParser, args: argparse.Namespace, backend: Backend
) -> None:
    if args.output is not None and len(args.targets) > 1:
        parser.error("-o names one file, so it takes one --to language with a text")
    text = text_file.read(args.file)
    for target in args.targets:
        output: Path = args.output or text_file.output_path(args.file, target)
        # A translation that is already there may have been corrected by hand.
        if output.exists():
            print(f"{target}: {output} already exists, left as it is")
            continue
        translated, count = text_file.translate_text(
            backend,
            text,
            source=args.source,
            target=target,
            progress=_progress(target),
        )
        text_file.write(output, translated)
        print(f"{target}: {count} paragraphs translated -> {output}")


def _api_address(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError(f"not an http(s) address: {value!r}")
    return value


def _progress(target: str) -> Progress | None:
    if not sys.stderr.isatty():
        return None

    def show(done: int, total: int) -> None:
        end = "\n" if done == total else ""
        print(f"\r{target}: {done}/{total}", end=end, file=sys.stderr, flush=True)

    return show

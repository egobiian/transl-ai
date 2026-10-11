"""Command-line entry point."""

import argparse
from collections.abc import Sequence
from importlib import metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transl-ai",
        description="Translate Godot CSV localization files with Ollama.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {metadata.version('transl-ai')}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0

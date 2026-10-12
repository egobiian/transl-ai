"""Read settings, such as API keys, from a `.env` file."""

import os
from collections.abc import MutableMapping
from pathlib import Path


def load_env_file(path: Path, environ: MutableMapping[str, str] | None = None) -> None:
    """Add the `NAME=value` lines of `path` to the environment.

    A variable that is already set wins. An empty value is skipped: a key set to
    nothing would hide the credentials a provider's client finds by other means.
    A file that is not there is not an error.
    """
    target = os.environ if environ is None else environ
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return
    for line in text.splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not name or name.startswith("#"):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            target.setdefault(name, value)

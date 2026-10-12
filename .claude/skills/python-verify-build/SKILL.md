---
name: python-verify-build
description: Pre-commit gate for Python projects. Use before every commit that touches source in a Python project, or when asked to verify, check or validate a Python change. Verifies types with the project's type checker, lint and formatting, the test suite, the package build when the project is distributed, and that the changed code actually runs. Reports which gates ran and what they said.
---

# Verify a Python change before committing

Five gates, in order. Gates 1–3 always run. Gate 4 runs when the project is built into a package and the commit touches what goes into it. Gate 5 runs when the commit changes something that runs. A commit only happens when every gate that applies is green. Never report a gate as passing without having run it and read its output.

A commit that touches only documentation, or files no check reads, has no source to verify. Say so plainly and skip, rather than inventing a green run.

## Use the project's environment

Find the commands where the project declares them: `pyproject.toml`, a `Makefile` or `justfile`, `tox.ini` or `noxfile.py`, and the CI workflow. The CI workflow is the best single source: it is the list the project already agreed has to pass. The commands below show what each gate has to run, written for uv and the most common tools.

Run every tool through the project's environment — `uv run`, `poetry run`, the activated virtual environment. A linter or a type checker run from a global install checks the code against the wrong interpreter and the wrong dependencies. It cannot see the project's packages, so it either reports imports it cannot find or treats them as untyped and passes what it never checked.

When the commit changes dependencies, confirm first that the lockfile matches the manifest, with the tool's own check:

```bash
uv lock --check
```

`uv run` locks and syncs before it runs a command, so a stale lockfile is otherwise rewritten by the gate itself, and the working tree changes underneath the commit.

A gate the project does not have is reported as absent. It is not replaced with a tool of your own choosing, and it is never reported as passing.

## Gate 1 — Types

```bash
uv run mypy .    # or pyright: the checker the project configures, run as it configures it
```

Run the type checker with the project's configuration and nothing added. A flag that makes the errors go away is not a fix. `--ignore-missing-imports` is the usual one: everything that comes from the import is then treated as untyped, and passes.

Confirm that it reaches what the commit touched. A checker only looks at the paths it is given or configured with, and a new package outside them is skipped without a word.

## Gate 2 — Lint and format

```bash
uv run ruff check .
uv run ruff format --check .
```

Run whatever linter and formatter the project has, the formatter in check mode.

Check mode, never write mode: a gate that silently rewrites hides what the commit actually contains. `ruff check --fix`, and a formatter run without its check flag, both change the files and exit 0 — a green light that altered the working tree instead of inspecting it.

A lint failure is fixed at its cause, never with a `# noqa`.

## Gate 3 — Tests

```bash
uv run pytest
```

Run the whole suite. A `-k` filter or a single path is for iterating; as a gate it proves only what it selected.

Read the summary, not just the exit code:

- pytest exits 5 when it collects no tests. In a project that has tests, that is a failure: the runner is looking somewhere the tests are not, and every assertion is silently absent.
- Read the counts of skipped and expected-failure tests. A test that ran before the commit and is skipped after it is a finding, not a pass.
- Read the warnings. One raised by the code the commit touched is a failure here.

## Gate 4 — The package build

Skip when the project is never built into a distribution, or when the commit leaves the package's contents and its metadata untouched.

```bash
uv build    # or: python -m build
```

Tests run against the source tree, where every file is present. The wheel only contains what the build configuration includes, so a data file, a template or a `py.typed` marker can be missing from it while every test passes.

When the commit adds a file that is not Python source, list the wheel and confirm the file is in it:

```bash
python -m zipfile -l dist/<name>.whl
```

Then install the wheel into a clean environment outside the repository and import the package from there. An import that works only from the source tree is the failure this gate exists to catch.

## Gate 5 — Run what changed

Skip only when the commit changes nothing that runs.

The earlier gates prove the code is well-formed and that its tests pass. None of them proves that the program starts, or that the change does what it should. So run it and drive the path the commit touched, end to end.

- Exercise the code path the commit actually changed, through the entry point a user would use. A help message verifies nothing about a new command.
- Throwaway scripts live in a scratch directory outside the repository, and are never committed.
- Never touch the project's real data. Ask the system for a free port instead of using a fixed one, and use an in-memory or temporary database, so the run cannot collide with something already running or destroy what is there.
- Always shut down what you started. A run that hangs is a failed gate: something is holding the process open.
- Read all the output. A traceback, a warning or an unawaited-coroutine notice is a failure here even when the process exits 0.

## Reporting

State plainly which gates ran, which were skipped or absent and why, and what each said. If a gate fails, fix the cause and re-run from Gate 1. Never commit around a failure, and never describe a skipped gate as passing.

Passing the gates is not the same as the work being right. The gates catch what a machine can catch.

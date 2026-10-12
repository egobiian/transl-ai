---
name: verify-build
description: Pre-commit gate for any project. Use before every commit that touches source, or when asked to verify, check or validate a change before committing or opening a pull request. Finds the project's own type check, lint, test and build commands, runs them in order, and exercises what the change touched against the built result. Reports which gates ran and what they said. When the project has a verification skill for its own stack, use that one instead.
---

# Verify the build before committing

Five gates, in order. A commit only happens when every gate that applies is green. Never report a gate as passing without having run it and read its output.

A commit that touches only documentation, or files the build never reads, has no source to verify. Say so plainly and skip, rather than inventing a green run.

## Find the gates first

The project defines its checks; you do not. Read where it declares them — the `package.json` scripts, a `Makefile` or `justfile`, `pyproject.toml`, the CI workflow — and use those commands as written. The CI configuration is the best single source: it is the list the project already agreed has to pass.

A gate the project does not have is reported as absent. It is not replaced with a command of your own choosing, and it is never reported as passing.

## Gate 1 — Types

Run the project's type check. For a compiled language, that is the compilation itself.

Use the project's script rather than calling the compiler directly. A bare compiler call can check far less than it appears to: pointed at a root configuration that only references sub-projects it finds no inputs, and template formats it does not understand are skipped without a word. Either way it exits 0 having verified nothing.

When the commit adds a package or a project directory, confirm that the type check actually reaches it.

## Gate 2 — Lint and format

Run the linters, and the formatter in **check** mode.

Check mode, never write mode: a gate that silently reformats hides what the commit actually contains. If the project only has a script that writes, do not append a check flag to it. The write flag is still in the script, so the formatter fixes the files and exits 0 — a green light that changed the working tree instead of inspecting it. Call the formatter's check mode directly.

A lint failure is fixed at its cause, never with a disable comment.

## Gate 3 — Tests

Run the test suite and read the summary, not just the exit code.

When the project has tests, a run that reports no tests found is a failure, not a pass. It means the runner is looking somewhere the tests are not, and every assertion in the suite is silently absent. Read the count.

Never skip this gate on the grounds that the change has nothing to test. Run it and read what it says.

## Gate 4 — The production build

Run the build that ships, not the development one.

Type checks and tests run against modules in isolation. The build resolves the real graph: a missing asset, a bad import path or a dependency absent from the manifest all pass the earlier gates and fail only here.

Read the whole output. Build tools report warnings — an unresolved import chief among them — while still exiting 0, and each of those is a failure here.

## Gate 5 — Run what changed

Skip only when the commit changes nothing that runs.

The first four gates prove the project compiles. None of them proves that it starts, or that the change does what it should. So run the built result and drive the path the commit touched, end to end.

- Exercise the code path the commit actually changed. A start-up banner verifies nothing about a new feature.
- Run against the built result, not the development server. The development server does not serve what ships.
- Throwaway scripts live in a scratch directory outside the repository, and are never committed.
- Never touch the project's real data. Ask the system for a free port instead of using a fixed one, and use an in-memory or temporary database, so the run cannot collide with something already running or destroy what is there.
- Always shut down what you started. A run that hangs is a failed gate: something is holding the process open.
- Read all the output. Warnings and unhandled errors are failures here even when the process exits 0.
- A change to what a user sees is not verified until it has been opened and looked at. Automated checks assert on structure; they have no opinion about whether the result reads well.

## Reporting

State plainly which gates ran, which were skipped or absent and why, and what each said. If a gate fails, fix the cause and re-run from Gate 1. Never commit around a failure, and never describe a skipped gate as passing.

Passing the gates is not the same as the work being right. The gates catch what a machine can catch.

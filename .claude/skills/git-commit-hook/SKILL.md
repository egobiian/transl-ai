---
name: git-commit-hook
description: Installs a commit-msg git hook that enforces single-line Conventional Commit headers — a known type, no scope, no "!" marker, a lowercase description, no trailing period, 72 characters at most, and no body, footers or trailers. Use when setting up a repository, when asked to enforce the commit convention or to add a commit hook, or when commits that break the convention are getting through.
---

# Install the commit message hook

The hook in [assets/commit-msg](assets/commit-msg) rejects any commit whose message is not exactly:

```
<type>: <description>
```

It checks the mechanical rules only: the type is one of `build` `chore` `ci` `docs` `feat` `fix` `perf` `refactor` `revert` `style` `test`, there is no scope and no `!` marker, the description starts lowercase and has no trailing period, the header is 72 characters at most, and the message is a single line. That last rule is what keeps bodies, footers and `Co-Authored-By:` trailers out of the history. Imperative mood and whether the description is worth reading are left to review.

Merge commits and the `fixup!`, `squash!` and `amend!` markers pass untouched. The hook needs only POSIX `sh` and git.

## Before installing

1. Check whether the repository already manages hooks: run `git config --get core.hooksPath`, and look for `.husky/`, `lefthook.yml` or `.pre-commit-config.yaml`.
2. If it does, install into that system instead of beside it. Two hook directories means one of them silently never runs.
3. If a `commit-msg` hook already exists, stop and show it to the user rather than overwriting it.

## Install

1. Copy `assets/commit-msg` from this skill's directory into the repository and make it executable:

   ```bash
   mkdir -p .githooks
   cp <this-skill>/assets/commit-msg .githooks/commit-msg
   chmod +x .githooks/commit-msg
   ```

2. Point git at the directory:

   ```bash
   git config core.hooksPath .githooks
   ```

3. Make it hold for every clone. `core.hooksPath` is local configuration and is not committed, so a fresh clone runs no hooks until that command runs there.

   In a Node project, add it to the `prepare` script in `package.json`, so installing dependencies sets it:

   ```json
   "prepare": "git rev-parse --git-dir >/dev/null 2>&1 && git config core.hooksPath .githooks || true"
   ```

   The guard keeps the install from failing where there is no git directory, such as a container build. If a `prepare` script already exists, chain onto it rather than replacing it.

   In any other project, add the command to the setup steps of the README.

4. Stop Claude Code from adding its trailer. By default it appends a `Co-Authored-By:` line to the commits it makes, which the hook rejects as a second line. Merge this key into `.claude/settings.json`, keeping whatever the file already holds:

   ```json
   {
     "attribution": {
       "commit": ""
     }
   }
   ```

## Verify

Run the hook directly against a message file. Nothing is committed.

```bash
f=$(mktemp)

printf 'feat: add email validation\n' > "$f"
.githooks/commit-msg "$f"; echo "exit $?"        # exit 0

printf 'feat(auth): add email validation\n' > "$f"
.githooks/commit-msg "$f"; echo "exit $?"        # exit 1, "no scope"

printf 'fix: handle empty input\n\nA longer explanation.\n' > "$f"
.githooks/commit-msg "$f"; echo "exit $?"        # exit 1, "one line only"

rm "$f"
```

Then confirm that `git config --get core.hooksPath` prints `.githooks`.

## Rules

- Never weaken the hook to let a commit through, and never bypass it with `--no-verify`. Fix the message.
- Changing what the convention allows, such as a scope or a body, is the user's decision. Ask before editing the hook.
- Report what you installed, what you changed in `package.json` and `.claude/settings.json`, and what the verification printed.

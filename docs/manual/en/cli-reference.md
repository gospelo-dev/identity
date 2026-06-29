# CLI Reference

Every subcommand follows these shared conventions:

- **stdout**: the command's intended output (table / profile name / prompt escapes, etc.)
- **stderr**: progress messages, warnings, and errors
- **exit code**:
  - `0` success / match
  - `1` expected condition not met (mismatch, no profile resolved, etc. — predictable failures)
  - `2` tool error (missing config, invalid YAML, external tool failure, etc.)

`prompt` is the only exception: it always returns exit 0 so it never breaks shell prompt rendering.

## Common

```
gospelo-identity --help        # List subcommands
gospelo-identity --version     # Print version
```

The config file path can be overridden with the `GOSPELO_IDENTITY_CONFIG` environment variable (mainly for testing).

---

## init

```
gospelo-identity init [--force] [--from-template] [--show-example]
```

Creates `~/.config/gospelo-identity/config.yml`.

With no options, the command interactively prompts for profile fields. If the file already exists, you are asked to confirm overwrite. Use `--force` to skip the confirmation.

Non-interactive modes:

- `--from-template` — copies the bundled template (`gospelo_identity/templates/config.template.yml`) to `~/.config/gospelo-identity/config.yml` and opens it in `$EDITOR` (default: `vi`). Interactive prompts are skipped. If the file already exists you are asked `Overwrite? [y/N]` (skip with `--force`). After copying, replace placeholders such as `<your-name>` with real values.
- `--show-example` — writes the bundled template to stdout. Use shell redirection like `gospelo-identity init --show-example > my-config.yml` to write a custom path. Always exits 0.

`--from-template` and `--show-example` cannot be combined (exit 2).

Three sample configurations (basic / minimal / advanced) are also available under [examples/](https://github.com/gospelo-dev/identity/tree/main/examples).

| Exit code | Meaning |
|---|---|
| 0 | Saved successfully, kept the existing file, or `--show-example` succeeded |
| 1 | Aborted (Ctrl-C / EOF / overwrite refused) or no profile entered |
| 2 | I/O error during save, missing template, `--from-template` combined with `--show-example`, or `$EDITOR` binary not found |

---

## list

```
gospelo-identity list
```

Prints registered profiles as a table.

| Exit code | Meaning |
|---|---|
| 0 | At least one profile is registered |
| 1 | Profile list is empty (init normally prevents this, but kept for safety) |
| 2 | Config missing or invalid |

---

## detect

```
gospelo-identity detect [--cwd PATH]
```

Prints the profile name that matches the current directory (or the `--cwd` path) on a single line. Useful for scripts that only need the profile name.

| Exit code | Meaning |
|---|---|
| 0 | A profile was resolved |
| 1 | No profile matched and `default_profile` is not set |
| 2 | Config missing or invalid |

---

## check

```
gospelo-identity check [--cwd PATH]
```

Compares the expected profile against the actual state (`git config user.name` / `user.email` / the active `gh` CLI login) and prints the result as a table.

Example output:

```
=== Identity Check ===
Working dir: /Users/you/projects/gospelo-dev/review
Matched profile: oss (via pattern: ~/projects/gospelo-dev/**)

[git]
  user.name  : your-oss-login  (expected: your-oss-login )  OK
  user.email : you@example.com (expected: you@example.com)  OK
[gh CLI]
  login      : your-work-login (expected: your-oss-login )  NG

WARNING: gh CLI account does not match expected profile.
Run `gospelo-identity switch oss` to fix.
```

| Exit code | Meaning |
|---|---|
| 0 | All values match |
| 1 | One or more mismatches, or no profile could be resolved |
| 2 | Config missing or invalid, or external tool failure |

---

## switch

```
gospelo-identity switch <profile> [--global] [--dry-run] [--cwd PATH]
```

Sets `git config user.name` / `user.email` for the given profile and runs `gh auth switch -u <account>`.

- Default scope is `git config --local` (current repository only)
- `--global` applies user-wide
- `--dry-run` shows the planned actions without any side effects

| Exit code | Meaning |
|---|---|
| 0 | Both git config and gh switch succeeded |
| 1 | Partial success (one of the two failed) |
| 2 | Profile not found, both failed, or external tool missing |

When `--local` (the default) is used and `cwd` is outside a git work tree, the command stops with exit 2. Either pass `--global` or move into a repository.

---

## prompt

```
gospelo-identity prompt [--format {plain,color,ps1}] [--show-mismatch] [--cwd PATH]
```

Helper for shell prompt integration. Prints the matched profile name in the form `[name]`. Returns an empty string when nothing matches or the config is missing. Always exits 0.

`--format`:

- `plain` (default) — `[oss]`
- `color` — wrapped in ANSI escapes (`\033[33m[oss]\033[0m`)
- `ps1` — wrapped in bash readline non-printing markers `\[ \]` for use in `PS1`

When `--show-mismatch` is set, an `!` is appended (`[oss !]`) when the git/gh state does not match the profile, and the marker is rendered in red under `color` / `ps1`.

bash example:

```bash
PS1='$(gospelo-identity prompt --format=ps1 --show-mismatch) \w \$ '
```

zsh example (requires `setopt PROMPT_SUBST` when used in `PROMPT`):

```zsh
setopt PROMPT_SUBST
PROMPT='%F{yellow}$(gospelo-identity prompt --format=plain --show-mismatch)%f %~ %# '
```

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

---

## Enforcement: guard (gh/git PATH shim)

The guard shadows `gh` (and optionally `git`) on your `PATH` with tiny shim executables. Every call is routed through `gospelo-identity guard`, which lets **read-only** commands through untouched and, for **write / outward-facing** commands (`git push`; `gh release/pr/repo/... create`; mutating `gh api`; etc.), runs the current directory's identity check first — **blocking** the write (non-zero exit, the real binary is never executed) when the active git/gh identity does not match the profile that owns the directory.

Design constraints:

- **Deterministic** — pure pattern logic, never an LLM.
- **Local** — nothing leaves the machine beyond the `gh api user` call that `check` already makes.
- **Fail-open outside enforcement** — a write under a matched profile with a mismatched identity is blocked; everywhere else (no config, unreadable config, a directory governed by no profile, or `GOSPELO_IDENTITY_SKIP` set) the real command runs unchanged, so the guard never breaks unrelated work.

Limitation: a `PATH` shim only intercepts **name-based** calls. A command invoked by absolute path (`/usr/bin/git push`) bypasses it. The shim's job is to stop *accidental* wrong-identity writes during automation / agent runs — not to resist an adversarial process. Layer an OS sandbox for that.

### install-guard

```
gospelo-identity install-guard [--dir DIR] [--tools gh,git]
```

Writes shim executables into `DIR` (default `~/.gospelo-identity/bin`) and prints the line to add to your shell rc.

- `--tools` (default `gh`) — comma-separated tools to shadow. Shadowing `git` adds Python startup to every `git` call and a large blast radius, so opt in explicitly with `--tools gh,git` only if you want `git push` guarded. (Commit-message hygiene is handled separately by `install-commit-hook`.)
- Before installing, the command verifies that the resolved `gospelo-identity` actually supports the `guard` subcommand, and refuses to install broken shims (e.g. when a stale build is first on `PATH`).

Activate by putting the shim dir at the **front** of `PATH`:

```bash
export PATH="$HOME/.gospelo-identity/bin:$PATH"   # add to ~/.zshrc or ~/.bashrc
command -v gh   # should print the shim path
```

| Exit code | Meaning |
|---|---|
| 0 | At least one shim was installed |
| 1 | No shims installed (tool not found on `PATH`, or the resolved command lacks `guard`) |

### guard

```
gospelo-identity guard --tool {gh,git} --real <path> -- <args...>
```

The runtime gate that the shims call; you do not normally run it by hand. For **write** invocations it prints a one-line status to **stderr** (read-only invocations stay silent):

| Situation | stderr | Result |
|---|---|---|
| identity matches | `identity OK for profile '<name>'; passing through.` | real command runs |
| identity mismatch | `BLOCKED ... fix: gospelo-identity switch <name>` | **blocked**, exit 1 |
| directory not governed | `directory not governed by any profile; passing through.` | real command runs |
| no / unreadable config | `no usable config; passing through ...` | real command runs |

Environment variables:

- `GOSPELO_IDENTITY_SKIP=1` — bypass the gate for a single call: `GOSPELO_IDENTITY_SKIP=1 gh release create ...`.
- `GOSPELO_IDENTITY_QUIET=1` — suppress the informational stderr status lines above. A **BLOCK is always reported**, regardless of this setting.

### uninstall-guard

```
gospelo-identity uninstall-guard [--dir DIR] [--tools gh,git]
```

Removes the shim files. Remember to also remove the `export PATH=...` line you added to your shell rc.

---

## Enforcement: commit-msg hook (strip Co-Authored-By)

A global `commit-msg` hook removes every `Co-authored-by:` trailer from commit messages — the human running the commit is the accountable author. Unlike the PATH shim, the hook fires even when `git` is invoked by absolute path or by an IDE (git itself runs it), and it adds no per-call latency (it runs only at commit time).

### install-commit-hook

```
gospelo-identity install-commit-hook [--dir DIR] [--force]
```

Installs a global `core.hooksPath` dispatcher in `DIR` (default `~/.gospelo-identity/git-hooks`) that strips `Co-Authored-By` on `commit-msg` and then **chains to each repository's own `.git/hooks/<name>`**, so existing hooks (husky, pre-commit, …) keep working.

- If a global `core.hooksPath` is already set to a different value, the command refuses unless `--force` is given.
- Repositories that set their **own** `core.hooksPath` (e.g. husky) override the global one; install per-repo there.

| Exit code | Meaning |
|---|---|
| 0 | Installed |
| 1 | A different global `core.hooksPath` already exists (re-run with `--force`) |
| 2 | Failed to set `core.hooksPath` |

### uninstall-commit-hook

```
gospelo-identity uninstall-commit-hook [--dir DIR]
```

Unsets the global `core.hooksPath` (only if it points at our dispatcher) and removes the dispatcher files.

### strip-coauthors

```
gospelo-identity strip-coauthors <commit-msg-file>
```

The worker that the hook invokes; it rewrites the message file in place, removing `Co-authored-by:` lines. You normally never call this directly. Always exits 0 (it never blocks a commit on its own I/O error).

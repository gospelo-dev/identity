---
name: gospelo-identity-check
description: Verify git/gh CLI identity matches the expected profile before any write operation (push, PR, release, package publish). Stops the operation on mismatch and surfaces the exact fix command.
trigger: pre-write
keywords:
  - identity
  - account
  - profile
  - switch
  - push
  - publish
  - release
  - merge
  - deploy
  - 公開
  - マージ
  - デプロイ
priority: high
---

# gospelo-identity Skill (Claude Code)

## Purpose

Prevent accidental commits, pushes, releases, or package publishes under the
wrong GitHub account when the user maintains multiple identities (personal OSS
/ employer / clients).

This skill wraps the `gospelo-identity` CLI as an automatic pre-flight check.
On every write-to-remote operation, the agent verifies that the current working
directory's expected profile matches what `git config` and `gh auth status`
actually report.

## When to invoke

Invoke this skill **before** executing any of the following operations:

### Git operations

- `git push` (any remote)
- `git push --force` / `--force-with-lease`
- `git push origin main` / `git push origin master`
- `git commit` when the user explicitly says "commit and push"

### GitHub CLI operations

- `gh pr create`
- `gh pr merge`
- `gh pr review --approve`
- `gh release create`
- `gh workflow run`
- `gh repo create`

### Package publishing

- `pip publish`, `python -m build && twine upload`
- `npm publish`, `yarn publish`, `pnpm publish`
- `cargo publish`
- `docker push`, `docker login` (when followed by push)
- `gem push`
- `mvn deploy`, `gradle publish`

### Natural language triggers

Invoke when the user's instruction includes (case-insensitive):

- English: `publish`, `release`, `push`, `deploy`, `merge`, `ship`
- Japanese: `公開`, `マージ`, `デプロイ`, `リリース`, `プッシュ`

### Directory entry

Also invoke once when the agent enters (`cd` or new session in) a directory
that matches one of the `paths` globs in `~/.config/gospelo-identity/config.yml`.

## How to invoke

Run `gospelo-identity check` in the current working directory:

```bash
gospelo-identity check
```

Then branch on the exit code:

| Exit code | Meaning | Action |
|---|---|---|
| `0` | Identity matches expected profile | Continue silently with the planned write operation |
| `1` | Identity mismatch detected | **STOP** the write operation and show the fix to the user (see below) |
| `2` | Tool error (no config, invalid YAML, `gh` not authenticated, etc.) | Surface the error verbatim to the user and ask how to proceed |

Do **not** assume a default identity when exit code is `2`. Per the
gospelo-identity project policy there is no silent fallback — surface the error.

## Action on mismatch (exit code 1)

When `gospelo-identity check` returns `1`, do **not** proceed with the planned
write operation. Display the following to the user (using the actual values
from the `check` output):

```
Identity mismatch detected.

  Expected profile: <profile_name>
  Mismatched fields:
    - <field>: expected <expected>, actual <actual>
    - <field>: expected <expected>, actual <actual>

Fix (one-shot switch of git config + gh CLI account):

  gospelo-identity switch <profile_name>

Per-directory direnv override (recommended for repos you visit often):

  echo 'export GH_TOKEN="$(gh auth token --user <login>)"' > .envrc
  direnv allow

Re-run the requested operation after the identity is corrected.
```

Then wait. Do not retry the write operation until the user either:

1. Runs the suggested `gospelo-identity switch` command (or fixes manually),
   and confirms — at which point you should re-run `gospelo-identity check`
   to verify, then proceed.
2. Explicitly overrides with phrasing such as "override", "force", "強制実行",
   "無視して進めて", or "ignore the mismatch and continue". Only then proceed
   with the original write operation.

The default behavior is to **block**, not to confirm-and-proceed.

## Action on tool error (exit code 2)

Surface the stderr from `gospelo-identity check` to the user verbatim. Common
causes and what to suggest:

- **Config file not found**: suggest `gospelo-identity init` (or
  `gospelo-identity init --from-template` for a non-interactive template).
- **`gh` not authenticated**: suggest `gh auth login` for the relevant account.
- **Invalid YAML**: suggest opening
  `~/.config/gospelo-identity/config.yml` and fixing the syntax.

Do not silently continue. Do not assume a default profile.

## Installation

```bash
# 1. Install the gospelo-identity CLI
pip install gospelo-identity

# 2. Create the config (interactive)
gospelo-identity init

# 3. Verify it works in the current directory
gospelo-identity check
```

Place this skill at one of:

- **Per-project**: `.claude/skills/gospelo-identity-check/skill.md`
- **Global (all projects)**: `~/.claude/skills/gospelo-identity-check/skill.md`

The skill file itself is the entire skill — no scripts to vendor; the
`gospelo-identity` binary on `PATH` does the work.

## Notes for the agent

- This skill should add **zero** visible output when identity is correct.
  Only speak up on mismatch or error.
- Do not run `gospelo-identity switch` automatically on the user's behalf
  unless the user has explicitly asked for it — the user may want to
  understand the mismatch first.
- The expected profile is determined by the longest-matching `paths` glob in
  the user's config; the skill should not second-guess this.

## See also

- [gospelo-identity GitHub](https://github.com/gospelo-dev/identity)
- [Shell integration (direnv, PS1)](https://github.com/gospelo-dev/identity/blob/main/docs/manual/ja/shell-integration.md)
- [CLI reference](https://github.com/gospelo-dev/identity/blob/main/docs/manual/ja/cli-reference.md)

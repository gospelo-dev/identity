# gospelo-identity - Directory-aware git/gh CLI identity guard
# Copyright (c) 2026 NoStudio LLC. All rights reserved.
# Licensed under the MIT License. See LICENSE.md for details.

"""Thin wrappers around ``git`` and ``gh`` CLI subprocess calls.

These helpers keep the actual command construction in one place so the rest
of the package can stay focused on logic. Errors are surfaced as
``ExternalToolError`` for the CLI to translate into exit code 2.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ExternalToolError(Exception):
    """Raised when an external tool is missing or returns a fatal error."""


@dataclass
class CommandResult:
    """Captured result of a subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise ExternalToolError(
            f"Required external tool not found on PATH: {tool!r}"
        )


def _run(args: list[str], cwd: Path | None = None) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExternalToolError(
            f"Failed to invoke {' '.join(args)}: {exc}"
        ) from exc
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )


# ---- git -------------------------------------------------------------------


def git_get_config(key: str, cwd: Path | None = None) -> str | None:
    """Return ``git config <key>`` for the given cwd, or ``None`` if unset."""
    _require("git")
    result = _run(["git", "config", "--get", key], cwd=cwd)
    if result.returncode == 0:
        return result.stdout or None
    if result.returncode == 1:
        # `git config --get` exits 1 when the key is not set; not an error.
        return None
    raise ExternalToolError(
        f"git config --get {key} failed (exit {result.returncode}): "
        f"{result.stderr or result.stdout}"
    )


def git_set_config(
    key: str, value: str, *, scope: str = "local", cwd: Path | None = None
) -> None:
    """Set ``git config <key> <value>``.

    ``scope`` is one of ``local``, ``global``, ``system``.
    """
    _require("git")
    if scope not in ("local", "global", "system"):
        raise ValueError(f"invalid scope: {scope!r}")
    args = ["git", "config", f"--{scope}", key, value]
    result = _run(args, cwd=cwd)
    if result.returncode != 0:
        raise ExternalToolError(
            f"{' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr or result.stdout}"
        )


def git_inside_work_tree(cwd: Path | None = None) -> bool:
    """Return True if ``cwd`` is inside a git working tree."""
    _require("git")
    result = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return result.returncode == 0 and result.stdout == "true"


# ---- gh --------------------------------------------------------------------


def gh_active_login() -> str | None:
    """Return the login name of the currently active gh CLI account.

    Returns ``None`` if gh CLI is not authenticated.
    """
    _require("gh")
    result = _run(["gh", "api", "user", "--jq", ".login"])
    if result.returncode == 0 and result.stdout:
        return result.stdout
    return None


def gh_logged_in_accounts() -> list[str]:
    """Return all gh CLI accounts the user is currently authenticated as."""
    _require("gh")
    result = _run(["gh", "auth", "status"])
    # gh auth status prints to stderr regardless of result.
    text = (result.stderr or "") + "\n" + (result.stdout or "")
    accounts: list[str] = []
    for line in text.splitlines():
        # Looking for: "  - Logged in to github.com account <login> (...)"
        marker = "Logged in to github.com account "
        idx = line.find(marker)
        if idx >= 0:
            tail = line[idx + len(marker):].strip()
            login = tail.split()[0] if tail else ""
            if login:
                accounts.append(login)
    return accounts


def gh_switch_account(account: str) -> None:
    """Run ``gh auth switch -u <account>``."""
    _require("gh")
    args = ["gh", "auth", "switch", "-u", account]
    result = _run(args)
    if result.returncode != 0:
        raise ExternalToolError(
            f"{' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr or result.stdout}\n"
            f"Hint: run `gh auth login --hostname github.com` "
            f"to add the account first."
        )

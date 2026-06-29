# gospelo-identity - Directory-aware git/gh CLI identity guard
# Copyright (c) 2026 NoStudio LLC. All rights reserved.
# Licensed under the MIT License. See LICENSE.md for details.

"""``gospelo-identity check`` command.

Compares the expected profile (resolved from cwd) against actual local
``git config`` and the active ``gh`` CLI account, then prints a table.

Exit codes:
  0 - everything matches
  1 - one or more values mismatch, or no profile matched the directory
  2 - configuration or external tool error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import _external
from .config import ConfigError, Profile, load_config
from .matcher import resolve_profile


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gospelo-identity check",
        description=(
            "Compare expected profile (resolved from the current directory) "
            "against actual git config + gh CLI active account."
        ),
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Override the directory to test against (default: current).",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    cwd = (args.cwd if args.cwd is not None else Path.cwd()).resolve()
    match = resolve_profile(config, cwd)

    print("=== Identity Check ===")
    print(f"Working dir: {cwd}")

    if not match.matched:
        print("Matched profile: (none)")
        print(
            "\nERROR: no profile path matched this directory and no "
            "default_profile is set.",
            file=sys.stderr,
        )
        sys.exit(1)

    expected: Profile = match.profile
    via = " (default)" if match.via_default else f" (via pattern: {match.matched_pattern})"
    print(f"Matched profile: {expected.name}{via}")
    print()

    try:
        actual_name = _external.git_get_config("user.name", cwd=cwd)
        actual_email = _external.git_get_config("user.email", cwd=cwd)
        actual_login = _external.gh_active_login()
    except _external.ExternalToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    rows: list[tuple[str, str, str, str, bool]] = [
        (
            "git",
            "user.name",
            actual_name or "(unset)",
            expected.git_user_name,
            actual_name == expected.git_user_name,
        ),
        (
            "git",
            "user.email",
            actual_email or "(unset)",
            expected.git_user_email,
            actual_email == expected.git_user_email,
        ),
        (
            "gh CLI",
            "login",
            actual_login or "(unauthenticated)",
            expected.gh_account,
            actual_login == expected.gh_account,
        ),
    ]

    name_w = max(len(r[1]) for r in rows)
    actual_w = max(len(r[2]) for r in rows)
    expected_w = max(len(r[3]) for r in rows)

    current_section = ""
    for section, key, actual, expected_value, ok in rows:
        if section != current_section:
            print(f"[{section}]")
            current_section = section
        status = "OK" if ok else "NG"
        print(
            f"  {key.ljust(name_w)} : "
            f"{actual.ljust(actual_w)}   "
            f"(expected: {expected_value.ljust(expected_w)})  {status}"
        )

    all_ok = all(r[4] for r in rows)
    print()
    if all_ok:
        print(f"OK: identity matches profile {expected.name!r}.")
        sys.exit(0)

    if not (rows[2][4]):
        print(
            f"WARNING: gh CLI account does not match expected profile.\n"
            f"Run `gospelo-identity switch {expected.name}` to fix.\n"
            f"If `switch` reports success but this stays NG, the stored "
            f"credential for {expected.gh_account!r} is stale (keyring mismatch); "
            f"re-login:\n"
            f"  gh auth logout --hostname github.com --user {expected.gh_account}\n"
            f"  gh auth login  --hostname github.com",
            file=sys.stderr,
        )
    else:
        print(
            f"WARNING: git config does not match expected profile.\n"
            f"Run `gospelo-identity switch {expected.name}` to fix.",
            file=sys.stderr,
        )
    sys.exit(1)


if __name__ == "__main__":
    main()

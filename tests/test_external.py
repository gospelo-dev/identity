# gospelo-identity - Directory-aware git/gh CLI identity guard
# Copyright (c) 2026 NoStudio LLC. All rights reserved.
# Licensed under the MIT License. See LICENSE.md for details.

"""Tests for ``gospelo_identity._external``.

Covers the thin git / gh CLI wrappers via ``mock_subprocess``. No real
``git`` or ``gh`` binary is invoked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gospelo_identity import _external
from gospelo_identity._external import ExternalToolError


# ---------------------------------------------------------------------------
# git_get_config
# ---------------------------------------------------------------------------


def test_git_get_config_returns_value(mock_subprocess) -> None:
    mock_subprocess.set("git config --get user.name", returncode=0, stdout="alice\n")
    assert _external.git_get_config("user.name") == "alice"
    # Confirm the exact command shape is right.
    assert any("git config --get user.name" in call for call in mock_subprocess.calls)


def test_git_get_config_missing_key_returns_none(mock_subprocess) -> None:
    # `git config --get` exits 1 when the key is unset; that is *not* an error.
    mock_subprocess.set("git config --get user.name", returncode=1, stdout="")
    assert _external.git_get_config("user.name") is None


def test_git_get_config_other_error_raises(mock_subprocess) -> None:
    mock_subprocess.set(
        "git config --get user.name",
        returncode=128,
        stdout="",
        stderr="fatal: not in a git repo",
    )
    with pytest.raises(ExternalToolError, match="git config --get user.name failed"):
        _external.git_get_config("user.name")


def test_git_get_config_passes_cwd(mock_subprocess, tmp_path: Path) -> None:
    mock_subprocess.set("git config --get user.email", returncode=0, stdout="a@b.com")
    result = _external.git_get_config("user.email", cwd=tmp_path)
    assert result == "a@b.com"


def test_git_get_config_tool_missing_raises(monkeypatch) -> None:
    monkeypatch.setattr("gospelo_identity._external.shutil.which", lambda t: None)
    with pytest.raises(ExternalToolError, match="not found on PATH"):
        _external.git_get_config("user.name")


# ---------------------------------------------------------------------------
# git_set_config
# ---------------------------------------------------------------------------


def test_git_set_config_local_scope(mock_subprocess) -> None:
    mock_subprocess.set("git config --local user.name alice", returncode=0)
    _external.git_set_config("user.name", "alice")
    # Default scope is local; must NOT see --global.
    last = mock_subprocess.calls[-1]
    assert "--local" in last
    assert "--global" not in last


def test_git_set_config_global_scope(mock_subprocess) -> None:
    mock_subprocess.set("git config --global user.name alice", returncode=0)
    _external.git_set_config("user.name", "alice", scope="global")
    last = mock_subprocess.calls[-1]
    assert "--global" in last


def test_git_set_config_invalid_scope_raises() -> None:
    with pytest.raises(ValueError, match="invalid scope"):
        _external.git_set_config("user.name", "alice", scope="bogus")


def test_git_set_config_failure_raises(mock_subprocess) -> None:
    mock_subprocess.set(
        "git config --local user.name",
        returncode=2,
        stderr="boom",
    )
    with pytest.raises(ExternalToolError, match="failed"):
        _external.git_set_config("user.name", "alice")


# ---------------------------------------------------------------------------
# git_inside_work_tree
# ---------------------------------------------------------------------------


def test_git_inside_work_tree_true(mock_subprocess) -> None:
    mock_subprocess.set("git rev-parse --is-inside-work-tree", returncode=0, stdout="true")
    assert _external.git_inside_work_tree() is True


def test_git_inside_work_tree_false(mock_subprocess) -> None:
    mock_subprocess.set(
        "git rev-parse --is-inside-work-tree",
        returncode=128,
        stdout="",
        stderr="fatal: not a git repo",
    )
    assert _external.git_inside_work_tree() is False


# ---------------------------------------------------------------------------
# gh_active_login
# ---------------------------------------------------------------------------


def test_gh_active_login_returns_login(mock_subprocess) -> None:
    mock_subprocess.set("gh api user --jq .login", returncode=0, stdout="alice")
    assert _external.gh_active_login() == "alice"


def test_gh_active_login_unauthenticated_returns_none(mock_subprocess) -> None:
    mock_subprocess.set(
        "gh api user --jq .login",
        returncode=1,
        stdout="",
        stderr="not authenticated",
    )
    assert _external.gh_active_login() is None


# ---------------------------------------------------------------------------
# gh_logged_in_accounts
# ---------------------------------------------------------------------------


def test_gh_logged_in_accounts_parses_status(mock_subprocess) -> None:
    status_output = (
        "github.com\n"
        "  - Logged in to github.com account alice (oauth_token)\n"
        "    Active account: true\n"
        "  - Logged in to github.com account bob (oauth_token)\n"
    )
    mock_subprocess.set("gh auth status", returncode=0, stderr=status_output)
    accounts = _external.gh_logged_in_accounts()
    assert accounts == ["alice", "bob"]


def test_gh_logged_in_accounts_empty_when_logged_out(mock_subprocess) -> None:
    mock_subprocess.set("gh auth status", returncode=1, stderr="not logged in")
    assert _external.gh_logged_in_accounts() == []


# ---------------------------------------------------------------------------
# gh_switch_account
# ---------------------------------------------------------------------------


def test_gh_switch_account_success(mock_subprocess) -> None:
    mock_subprocess.set("gh auth switch -u alice", returncode=0)
    _external.gh_switch_account("alice")
    assert any("gh auth switch -u alice" in c for c in mock_subprocess.calls)


def test_gh_switch_account_failure_raises(mock_subprocess) -> None:
    mock_subprocess.set(
        "gh auth switch -u nobody",
        returncode=1,
        stderr="account not found",
    )
    with pytest.raises(ExternalToolError, match="failed"):
        _external.gh_switch_account("nobody")


# ---------------------------------------------------------------------------
# _run / FileNotFoundError surface
# ---------------------------------------------------------------------------


def test_run_filenotfound_translates_to_external_tool_error(monkeypatch) -> None:
    """When ``subprocess.run`` itself raises FileNotFoundError (binary
    disappeared between ``which`` and ``run``), we wrap it."""

    def boom(*a, **kw):
        raise FileNotFoundError("git: not found")

    monkeypatch.setattr("gospelo_identity._external.shutil.which", lambda t: "/usr/bin/git")
    monkeypatch.setattr("gospelo_identity._external.subprocess.run", boom)
    with pytest.raises(ExternalToolError, match="Failed to invoke"):
        _external.git_get_config("user.name")


def test_command_result_dataclass() -> None:
    r = _external.CommandResult(returncode=0, stdout="x", stderr="")
    assert r.returncode == 0
    assert r.stdout == "x"

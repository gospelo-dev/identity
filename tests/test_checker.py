# gospelo-identity - Directory-aware git/gh CLI identity guard
# Copyright (c) 2026 NoStudio LLC. All rights reserved.
# Licensed under the MIT License. See LICENSE.md for details.

"""Tests for ``gospelo_identity.checker``.

Drives ``checker.main`` via ``monkeypatch`` of ``sys.argv`` and the
``mock_external`` fixture so no real ``git`` / ``gh`` is invoked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gospelo_identity import checker
from gospelo_identity._external import ExternalToolError


def _make_target_dir(tmp_home: Path) -> Path:
    target = tmp_home / "projects" / "personal" / "demo"
    target.mkdir(parents=True)
    return target


# ---------------------------------------------------------------------------
# Happy path (everything matches)
# ---------------------------------------------------------------------------


def test_check_all_match_exits_zero(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _make_target_dir(tmp_home)
    mock_external["git_user_name"] = "Alice Example"
    mock_external["git_user_email"] = "alice@example.com"
    mock_external["gh_login"] = "alice-personal"

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])

    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 0

    out = capsys.readouterr().out
    assert "OK" in out
    assert "personal" in out


# ---------------------------------------------------------------------------
# Mismatch cases
# ---------------------------------------------------------------------------


def test_check_user_name_mismatch_exits_one(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _make_target_dir(tmp_home)
    mock_external["git_user_name"] = "Wrong Name"
    mock_external["git_user_email"] = "alice@example.com"
    mock_external["gh_login"] = "alice-personal"

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "NG" in out


def test_check_user_email_mismatch_exits_one(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _make_target_dir(tmp_home)
    mock_external["git_user_name"] = "Alice Example"
    mock_external["git_user_email"] = "wrong@example.com"
    mock_external["gh_login"] = "alice-personal"

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 1


def test_check_gh_login_mismatch_exits_one(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _make_target_dir(tmp_home)
    mock_external["git_user_name"] = "Alice Example"
    mock_external["git_user_email"] = "alice@example.com"
    mock_external["gh_login"] = "alice-work"  # wrong account

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    # checker emits a "Run gospelo-identity switch ..." hint to stderr.
    assert "switch" in err


def test_check_all_mismatch_exits_one(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _make_target_dir(tmp_home)
    # Nothing matches.
    mock_external["git_user_name"] = "X"
    mock_external["git_user_email"] = "x@x"
    mock_external["gh_login"] = "x"

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# No matching profile
# ---------------------------------------------------------------------------


def test_check_no_matching_profile_no_default_exits_one(
    tmp_home: Path,
    write_config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without a default_profile, an unmatched cwd must exit 1."""
    cfg_yaml = (
        'version: "1"\n'
        "profiles:\n"
        "  solo:\n"
        "    git: {user.name: a, user.email: a@example.com}\n"
        "    gh: {account: solo}\n"
        "    paths: ['~/projects/specific/**']\n"
    )
    cfg = write_config(cfg_yaml)
    monkeypatch.setenv("GOSPELO_IDENTITY_CONFIG", str(cfg))

    nowhere = tmp_home / "elsewhere"
    nowhere.mkdir()
    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(nowhere)])

    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "no profile" in err.lower()


# ---------------------------------------------------------------------------
# External tool errors
# ---------------------------------------------------------------------------


def test_check_external_error_exits_two(
    isolated_config: Path,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = _make_target_dir(tmp_home)

    def boom(*a, **kw):
        raise ExternalToolError("git missing")

    monkeypatch.setattr("gospelo_identity._external.git_get_config", boom)
    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])

    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "ERROR" in err


def test_check_config_error_exits_two(
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing config file should produce exit 2 (config error), not 1."""
    monkeypatch.setenv(
        "GOSPELO_IDENTITY_CONFIG",
        str(tmp_home / "no-such-config.yml"),
    )
    monkeypatch.setattr("sys.argv", ["check"])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 2


def test_check_unset_git_config_shows_unset_marker(
    isolated_config: Path,
    mock_external,
    tmp_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When git config returns None, the report must show ``(unset)``."""
    target = _make_target_dir(tmp_home)
    mock_external["git_user_name"] = None
    mock_external["git_user_email"] = None
    mock_external["gh_login"] = None  # also unauthenticated

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit):
        checker.main()
    out = capsys.readouterr().out
    assert "(unset)" in out
    assert "(unauthenticated)" in out


def test_check_via_default_marker_in_output(
    tmp_home: Path,
    write_config,
    mock_external,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the default profile is used, output must say ``(default)``."""
    cfg_yaml = (
        'version: "1"\n'
        "profiles:\n"
        "  solo:\n"
        "    description: Bob\n"
        "    git: {user.name: bob, user.email: bob@example.com}\n"
        "    gh: {account: bob}\n"
        "    paths: ['~/never-here/**']\n"
        "default_profile: solo\n"
    )
    cfg = write_config(cfg_yaml)
    monkeypatch.setenv("GOSPELO_IDENTITY_CONFIG", str(cfg))

    target = tmp_home / "elsewhere"
    target.mkdir()

    mock_external["git_user_name"] = "bob"
    mock_external["git_user_email"] = "bob@example.com"
    mock_external["gh_login"] = "bob"

    monkeypatch.setattr("sys.argv", ["check", "--cwd", str(target)])
    with pytest.raises(SystemExit) as exc:
        checker.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "(default)" in out

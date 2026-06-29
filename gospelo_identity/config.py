# gospelo-identity - Directory-aware git/gh CLI identity guard
# Copyright (c) 2026 NoStudio LLC. All rights reserved.
# Licensed under the MIT License. See LICENSE.md for details.

"""Config loading and writing for gospelo-identity.

The config file lives at ``~/.config/gospelo-identity/config.yml`` and follows
the schema documented in ``docs/manual/ja/config-format.md``.

This module is deliberately strict: there are no silent fallbacks. If the file
is missing, the YAML is malformed, or a required key is absent, the caller
receives an exception that the CLI translates into a non-zero exit code with a
helpful message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH_ENV = "GOSPELO_IDENTITY_CONFIG"
DEFAULT_CONFIG_PATH = Path("~/.config/gospelo-identity/config.yml").expanduser()


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or invalid."""


@dataclass
class Profile:
    """One declared identity profile."""

    name: str
    description: str
    git_user_name: str
    git_user_email: str
    gh_account: str
    paths: list[str] = field(default_factory=list)


@dataclass
class Config:
    """Top-level config object."""

    version: str
    profiles: dict[str, Profile]
    default_profile: str | None
    source_path: Path

    def get_profile(self, name: str) -> Profile:
        """Return a profile by name, or raise ``ConfigError``."""
        if name not in self.profiles:
            available = ", ".join(sorted(self.profiles)) or "(none)"
            raise ConfigError(
                f"Unknown profile: {name!r}. Available: {available}"
            )
        return self.profiles[name]


def resolve_config_path() -> Path:
    """Return the active config file path.

    Honours ``GOSPELO_IDENTITY_CONFIG`` if set; otherwise uses the XDG-style
    default ``~/.config/gospelo-identity/config.yml``.
    """
    override = os.environ.get(CONFIG_PATH_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> Config:
    """Load and validate the config file.

    Raises ``ConfigError`` when the file is missing, the YAML is malformed,
    or required schema keys are absent. The caller is expected to catch this
    and surface a friendly message + exit code 2.
    """
    config_path = path if path is not None else resolve_config_path()

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}\n"
            f"Run `gospelo-identity init` to create one."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {config_path}: {exc}") from exc

    if raw is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    if not isinstance(raw, dict):
        raise ConfigError(
            f"Config file root must be a mapping, got {type(raw).__name__}"
        )

    return _parse_config(raw, config_path)


def _parse_config(raw: dict[str, Any], source_path: Path) -> Config:
    version = raw.get("version")
    if not version:
        raise ConfigError(
            f"{source_path}: missing required key 'version' (expected '1')"
        )
    if str(version) != "1":
        raise ConfigError(
            f"{source_path}: unsupported version {version!r}, this build "
            f"understands version '1' only"
        )

    profiles_raw = raw.get("profiles")
    if not isinstance(profiles_raw, dict) or not profiles_raw:
        raise ConfigError(
            f"{source_path}: missing or empty 'profiles' mapping"
        )

    profiles: dict[str, Profile] = {}
    for name, body in profiles_raw.items():
        profiles[name] = _parse_profile(name, body, source_path)

    default_profile = raw.get("default_profile")
    if default_profile is not None:
        if not isinstance(default_profile, str):
            raise ConfigError(
                f"{source_path}: 'default_profile' must be a string"
            )
        if default_profile not in profiles:
            raise ConfigError(
                f"{source_path}: 'default_profile' references unknown "
                f"profile {default_profile!r}"
            )

    return Config(
        version=str(version),
        profiles=profiles,
        default_profile=default_profile,
        source_path=source_path,
    )


def _parse_profile(name: str, body: Any, source_path: Path) -> Profile:
    if not isinstance(body, dict):
        raise ConfigError(
            f"{source_path}: profile {name!r} must be a mapping"
        )

    git_block = body.get("git")
    if not isinstance(git_block, dict):
        raise ConfigError(
            f"{source_path}: profile {name!r} missing required 'git' mapping"
        )

    user_name = git_block.get("user.name")
    user_email = git_block.get("user.email")
    if not isinstance(user_name, str) or not user_name.strip():
        raise ConfigError(
            f"{source_path}: profile {name!r} missing required "
            f"'git.user.name'"
        )
    if not isinstance(user_email, str) or not user_email.strip():
        raise ConfigError(
            f"{source_path}: profile {name!r} missing required "
            f"'git.user.email'"
        )

    gh_block = body.get("gh")
    if not isinstance(gh_block, dict):
        raise ConfigError(
            f"{source_path}: profile {name!r} missing required 'gh' mapping"
        )
    gh_account = gh_block.get("account")
    if not isinstance(gh_account, str) or not gh_account.strip():
        raise ConfigError(
            f"{source_path}: profile {name!r} missing required 'gh.account'"
        )

    paths_raw = body.get("paths", [])
    if not isinstance(paths_raw, list):
        raise ConfigError(
            f"{source_path}: profile {name!r} 'paths' must be a list"
        )
    paths: list[str] = []
    for entry in paths_raw:
        if not isinstance(entry, str) or not entry.strip():
            raise ConfigError(
                f"{source_path}: profile {name!r} 'paths' entries must be "
                f"non-empty strings"
            )
        paths.append(entry)

    description = body.get("description", "") or ""
    if not isinstance(description, str):
        raise ConfigError(
            f"{source_path}: profile {name!r} 'description' must be a string"
        )

    return Profile(
        name=name,
        description=description,
        git_user_name=user_name.strip(),
        git_user_email=user_email.strip(),
        gh_account=gh_account.strip(),
        paths=paths,
    )


def save_config(config: Config, path: Path | None = None) -> Path:
    """Serialise a ``Config`` back to YAML.

    The output path defaults to the config's ``source_path``. The parent
    directory is created with ``mode=0o700`` if missing. Existing files are
    overwritten without prompting; the CLI ``init`` command is responsible
    for asking before calling this.
    """
    target = path if path is not None else config.source_path
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    payload: dict[str, Any] = {"version": config.version, "profiles": {}}
    for name, profile in config.profiles.items():
        payload["profiles"][name] = {
            "description": profile.description,
            "git": {
                "user.name": profile.git_user_name,
                "user.email": profile.git_user_email,
            },
            "gh": {
                "account": profile.gh_account,
            },
            "paths": list(profile.paths),
        }
    if config.default_profile is not None:
        payload["default_profile"] = config.default_profile

    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    target.write_text(text, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        # Best-effort: fail open on filesystems that do not support chmod.
        pass
    return target

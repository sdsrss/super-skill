"""Path resolution. All roots are env-overridable so tests never touch the real
~/.super-skill state or the host's ~/.claude/skills directory."""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(var: str, default: str) -> Path:
    """Env-overridable path where EMPTY means unset (audit P0-1): an empty
    string would otherwise resolve to Path("") == CWD, turning the caller's
    working tree into state that `seed` git-commits."""
    return Path(os.environ.get(var) or default).expanduser()


def state_root() -> Path:
    """Registry + control state (git-backed in WS). docs/02 §4.1."""
    return _env_path("SUPER_SKILL_HOME", "~/.super-skill")


# Host distribution targets (docs/01 FR-PUB-2). Claude Code is the v1 default;
# Codex reads the open-standard ~/.agents/skills directly (docs/05 ADR-008).
HOSTS = ("claude", "codex")


def host_skills_dir(host: str = "claude") -> Path:
    """Skills directory for a host distribution target (env-overridable).

    claude -> ~/.claude/skills (SUPER_SKILL_HOST_SKILLS);
    codex  -> ~/.agents/skills (SUPER_SKILL_CODEX_SKILLS).

    An unknown host raises rather than silently falling back to the claude dir —
    a stray materialized_hosts entry must never write to the wrong host (review #3)."""
    if host == "codex":
        return _env_path("SUPER_SKILL_CODEX_SKILLS", "~/.agents/skills")
    if host != "claude":
        raise ValueError(f"unknown host {host!r} (expected one of: {', '.join(HOSTS)})")
    return _env_path("SUPER_SKILL_HOST_SKILLS", "~/.claude/skills")


def resolve_hosts(host: str) -> list[str]:
    """Expand a --host selector (claude | codex | all) to concrete host names."""
    if host == "all":
        return list(HOSTS)
    if host not in HOSTS:
        raise ValueError(f"unknown host {host!r} (expected one of: {', '.join(HOSTS)}, all)")
    return [host]


def registry_dir() -> Path:
    return state_root() / "registry"


def skills_dir() -> Path:
    return registry_dir() / "skills"

"""Path resolution. All roots are env-overridable so tests never touch the real
~/.super-skill state or the host's ~/.claude/skills directory."""

from __future__ import annotations

import os
from pathlib import Path


def state_root() -> Path:
    """Registry + control state (git-backed in WS). docs/02 §4.1."""
    return Path(os.environ.get("SUPER_SKILL_HOME", "~/.super-skill")).expanduser()


# Host distribution targets (docs/01 FR-PUB-2). Claude Code is the v1 default;
# Codex reads the open-standard ~/.agents/skills directly (docs/05 ADR-008).
HOSTS = ("claude", "codex")


def host_skills_dir(host: str = "claude") -> Path:
    """Skills directory for a host distribution target (env-overridable).

    claude -> ~/.claude/skills (SUPER_SKILL_HOST_SKILLS);
    codex  -> ~/.agents/skills (SUPER_SKILL_CODEX_SKILLS)."""
    if host == "codex":
        return Path(os.environ.get("SUPER_SKILL_CODEX_SKILLS", "~/.agents/skills")).expanduser()
    return Path(os.environ.get("SUPER_SKILL_HOST_SKILLS", "~/.claude/skills")).expanduser()


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

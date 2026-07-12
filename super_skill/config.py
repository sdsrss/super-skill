"""Path resolution. All roots are env-overridable so tests never touch the real
~/.super-skill state or the host's ~/.claude/skills directory."""

from __future__ import annotations

import os
from pathlib import Path


def state_root() -> Path:
    """Registry + control state (git-backed in WS). docs/02 §4.1."""
    return Path(os.environ.get("SUPER_SKILL_HOME", "~/.super-skill")).expanduser()


def host_skills_dir() -> Path:
    """Claude Code personal skills dir — v1 direct distribution target (R-SCOPE-3)."""
    return Path(os.environ.get("SUPER_SKILL_HOST_SKILLS", "~/.claude/skills")).expanduser()


def registry_dir() -> Path:
    return state_root() / "registry"


def skills_dir() -> Path:
    return registry_dir() / "skills"

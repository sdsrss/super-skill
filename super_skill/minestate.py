"""Mine watermark (D#67): remember how many distinct sessions had been captured
the last time the user mined, so ``status``/``mine`` can nudge once enough new
sessions have accumulated — "you solved X across N unmined sessions, run mine".

Deliberately tiny: one JSON file in the state root, overwritten (never appended)
each mine. Missing/corrupt reads as 0 so a fresh or hand-broken state degrades to
"everything is unmined" rather than crashing a read-only status.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_FILE = "mine_state.json"
_DEFAULT_THRESHOLD = 3


def reminder_threshold() -> int:
    """Distinct unmined sessions before status nudges (env-overridable)."""
    raw = os.environ.get("SUPER_SKILL_MINE_REMINDER")
    if raw is None:
        return _DEFAULT_THRESHOLD
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_THRESHOLD


def _path(root: Path) -> Path:
    return root / _FILE


def mined_sessions(root: Path) -> int:
    """Distinct-session count recorded at the last mine (0 if absent/corrupt)."""
    p = _path(root)
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return int(data["mined_sessions"])
    except (ValueError, KeyError, TypeError):
        return 0


def record_mined(root: Path, session_count: int) -> None:
    """Persist the current distinct-session count as the new watermark."""
    root.mkdir(parents=True, exist_ok=True)
    _path(root).write_text(
        json.dumps({"mined_sessions": session_count}), encoding="utf-8"
    )


def unmined(root: Path, current_sessions: int) -> int:
    """Distinct sessions captured since the last mine (clamped at 0)."""
    return max(0, current_sessions - mined_sessions(root))

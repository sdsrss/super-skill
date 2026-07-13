"""Mine watermark (D#67): remember WHICH distinct sessions had been mined last,
so ``status``/``mine`` can nudge once enough new sessions accumulate — "you
solved X across N unmined sessions, run mine".

It stores the SET of mined session ids, not a count (M13): the WAL is TTL-pruned
(FR-CAP-6), so an absolute count went silently wrong once old sessions rolled off — new
sessions could no longer exceed the stale high-water count. A set is robust:
unmined = current session ids not in the mined set.

Deliberately tiny: one JSON file in the state root, overwritten (never appended)
each mine. Missing/corrupt reads as the empty set so a fresh or hand-broken state
degrades to "everything is unmined" rather than crashing a read-only status.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
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


def mined_sessions(root: Path) -> set[str]:
    """Set of session ids mined last (empty set if absent/corrupt)."""
    p = _path(root)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data["mined_session_ids"])
    except (ValueError, KeyError, TypeError):
        return set()


def record_mined(root: Path, session_ids: Iterable[str]) -> None:
    """Persist the set of session ids seen at this mine as the new watermark."""
    root.mkdir(parents=True, exist_ok=True)
    p = _path(root)
    # Atomic write so a crash can't leave a truncated watermark (M12); a corrupt
    # read already degrades to empty, but atomicity keeps the good value intact.
    fd, tmp = tempfile.mkstemp(dir=root, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"mined_session_ids": sorted(set(session_ids))}, f)
    os.replace(tmp, p)


def unmined(root: Path, current_sessions: Iterable[str]) -> int:
    """How many currently-captured sessions have not been mined yet. Robust to
    WAL TTL pruning: pruned-and-mined sessions simply don't appear in current."""
    return len(set(current_sessions) - mined_sessions(root))

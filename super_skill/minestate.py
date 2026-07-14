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
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

_FILE = "mine_state.json"
# 3 re-fired at nearly every session opening for a heavy multi-session user
# (audit 2026-07-13); 20 keeps the nudge meaningful. 0 disables it entirely.
_DEFAULT_THRESHOLD = 20


def reminder_threshold() -> int:
    """Distinct unmined sessions before status nudges (env-overridable).

    0 = reminder disabled (see reminder_due). Invalid or negative values warn
    and fall back to the default, consistent with SUPER_SKILL_EVENT_TTL."""
    raw = os.environ.get("SUPER_SKILL_MINE_REMINDER")
    if raw is None:
        return _DEFAULT_THRESHOLD
    try:
        threshold = int(raw)
        if threshold < 0:
            raise ValueError
        return threshold
    except ValueError:
        print(
            f"ignoring invalid SUPER_SKILL_MINE_REMINDER={raw!r}; "
            f"using default {_DEFAULT_THRESHOLD}",
            file=sys.stderr,
        )
        return _DEFAULT_THRESHOLD


def reminder_due(unmined_count: int) -> bool:
    """True when the unmined backlog should nudge the user.

    Kept separate from a bare `>= threshold` comparison because threshold 0
    means OFF — the naive comparison made 0 an un-clearable perpetual nag
    (audit P2-13: mine can never bring unmined below 0)."""
    threshold = reminder_threshold()
    return threshold > 0 and unmined_count >= threshold


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

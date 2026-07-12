"""Coarse opportunity mining (docs/03 WS: "surface you solved X 3 times").

Clusters captured events into task families by keyword bigrams shared across
DISTINCT sessions, surfacing families that recur >=3 sessions — the FR-GEN-1
primary signal. This is the WS heuristic; the M2 Opportunity Miner with weighted
scoring (frequency/failure/verifier availability/...) is later.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from .schemas import CaptureEvent

_STOP = frozenset(
    "the a an and or of to in on for with without into from at by is are was were be this"
    " that these those it its as not no yes do did use used run running file files code"
    " error add change fix fixed test tests value values case cases new get set".split()
)


def _tokens(text: str) -> list[str]:
    out = []
    for t in re.sub(r"[^a-z0-9/_.\- ]", " ", text.lower()).split():
        t = t.strip("-./_")
        if len(t) >= 3 and not t.isdigit() and t not in _STOP:
            out.append(t)
    return out


def _event_text(ev: CaptureEvent) -> str:
    parts: list[str] = [ev.event_type]

    def walk(o: object) -> None:
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(ev.payload)
    return " ".join(parts)


@dataclass
class OpportunityFamily:
    label: str
    session_count: int
    event_count: int
    projects: set[str] = field(default_factory=set)


def mine_families(
    events: Iterable[CaptureEvent], *, min_sessions: int = 3
) -> list[OpportunityFamily]:
    """Return recurring keyword-bigram families sorted by session recurrence."""
    bg_sessions: dict[str, set[str]] = defaultdict(set)
    bg_events: dict[str, int] = defaultdict(int)
    bg_projects: dict[str, set[str]] = defaultdict(set)

    for ev in events:
        toks = _tokens(_event_text(ev))
        grams = {f"{toks[i]} {toks[i + 1]}" for i in range(len(toks) - 1)}
        for g in grams:
            bg_sessions[g].add(ev.session_id)
            bg_events[g] += 1
            if ev.project_id:
                bg_projects[g].add(ev.project_id)

    families = [
        OpportunityFamily(
            label=g,
            session_count=len(s),
            event_count=bg_events[g],
            projects=bg_projects[g],
        )
        for g, s in bg_sessions.items()
        if len(s) >= min_sessions
    ]
    families.sort(key=lambda f: (-f.session_count, -f.event_count))
    return families

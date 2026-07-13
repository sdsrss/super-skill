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

# Hook-envelope keys the CLI dumps wholesale into payload. They are metadata, not
# task content, and dominate families ("userpromptsubmit x", cwd-derived slugs) if
# mined — coarse mining should read content, not the envelope.
_ENVELOPE_KEYS = frozenset(
    "hook_event_name session_id event_id transcript_path cwd permission_mode"
    " timestamp consent_scope tool_name".split()
)

# Redaction leaves ``[REDACTED:kind]`` / ``~`` placeholders; drop the whole
# placeholder so "redacted" and the kind name don't become mined tokens.
_REDACTION_RE = re.compile(r"\[REDACTED:[^\]]*\]")

# Harness task-notification envelopes ride inside payload VALUES (e.g. a Stop
# event's last_assistant_message), so the envelope-KEY skip above can't see
# them. Their template prose dominated real mining (2026-07-12: 8 sessions /
# 31 events of "fires each time ... may notify more than once" bigrams).
# Strip metadata ELEMENTS wholesale (tag + inner text — ids, paths, template
# prose); other tags lose only their markup so <result> content still mines.
# Quantifiers are bounded (ReDoS guard): unmatched oversize elements degrade
# to tag-stripping, never to backtracking.
_HARNESS_ELEMENT_RE = re.compile(
    r"<(summary|note|task-id|tool-use-id|output-file|usage)\b[^>]{0,256}>"
    r".{0,4000}?</\1\s{0,8}>",
    re.S,
)
_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9_-]{0,64}[^>]{0,256}>")

# Metric names that also appear as bare key=value text outside any tag.
_HARNESS_STOP = frozenset(
    "task-notification task-id tool-use-id output-file"
    " subagent_tokens tool_uses duration_ms".split()
)

# CJK has no whitespace word boundaries, so the ASCII-only path below drops it
# entirely. Emit char-2grams from CJK runs as tokens so Chinese task content is
# minable (P0-1) — the ASCII tokenizer replaced every CJK char with a space, so
# a Chinese prompt yielded 0 tokens and those tasks were invisible to mining and
# systematically undercounted by GATE-1.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿]+")


def _tokens(text: str) -> list[str]:
    text = _HARNESS_ELEMENT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _REDACTION_RE.sub(" ", text)
    text = text.lower()
    out: list[str] = []
    # CJK runs -> adjacent-char 2grams (a lone char is too sparse to signal a
    # family); these flow into the same bigram recurrence counting as Latin tokens.
    for run in _CJK_RE.findall(text):
        out.extend(run[i : i + 2] for i in range(len(run) - 1))
    # Latin/ASCII path: strip CJK first so it isn't re-processed into noise.
    ascii_text = _CJK_RE.sub(" ", text)
    for t in re.sub(r"[^a-z0-9/_.\- ]", " ", ascii_text).split():
        t = t.strip("-./_")
        if len(t) >= 3 and not t.isdigit() and t not in _STOP and t not in _HARNESS_STOP:
            out.append(t)
    return out


def _event_text(ev: CaptureEvent) -> str:
    parts: list[str] = []

    def walk(o: object) -> None:
        if isinstance(o, str):
            parts.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in _ENVELOPE_KEYS:  # skip envelope metadata, mine content
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

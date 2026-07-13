"""Candidate approval loop (WS second half, docs/03: mine -> draft -> approve).

A *candidate* is a proposed skill drafted from a mined OpportunityFamily. It is
pre-promotion scratch: it lives under ``candidates/`` (git-ignored by the
registry) and is human-editable. Nothing reaches the production skill set until
``approve`` — the single write path that runs ``registry.add_version`` +
``materialize`` (git commit + copy to host). This preserves the One Writer Rule:
candidate -> gate (human approve) -> promote, never bypassed.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config
from .evallite import EvalError, eval_lite
from .gate import InstructionGateError, scan_skill_md
from .mine import OpportunityFamily
from .registry import Registry
from .schemas import (
    SCHEMA_VERSION,
    CandidateType,
    Provenance,
    ProvenanceKind,
    SkillStatus,
    SkillVersion,
    utcnow,
)
from .skillmd import parse

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Fingerprints of an unedited ``_draft_md`` scaffold. A candidate still carrying
# any of these is a hollow skill the human never filled in — block it at approve
# so it can't be promoted and start routing (audit P2-2). The phrases are specific
# to the template so a legitimate skill that merely mentions "TODO" isn't caught.
_TEMPLATE_MARKERS = ("EDIT before approving", "TODO: the trigger", "TODO: the procedure")


def _has_template_placeholder(raw: str) -> bool:
    return any(marker in raw for marker in _TEMPLATE_MARKERS)


def slugify(label: str) -> str:
    """Reduce a family label to an agentskills.io-legal skill name (may be empty;
    callers skip empties). Matches NAME_RE: lowercase alnum + single hyphens."""
    return _SLUG_RE.sub("-", label.lower()).strip("-")[:64].strip("-")


class CandidateError(RuntimeError):
    pass


class Candidate(BaseModel):
    """Persisted metadata for one drafted candidate (SKILL.md stored alongside)."""

    # extra="ignore" + schema_version: forward-tolerant read of candidate.json (P3-4).
    model_config = ConfigDict(extra="ignore")

    schema_version: int = SCHEMA_VERSION
    candidate_id: str
    family_label: str
    session_count: int
    event_count: int
    projects: list[str] = Field(default_factory=list)
    status: str = "pending"  # pending | approved | rejected
    skill_id: str | None = None
    version: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


def _draft_md(cand_id: str, fam: OpportunityFamily) -> str:
    """A stub SKILL.md the human is expected to edit before approving. WS coarse
    mining can name a recurring family, not write its procedure — so we scaffold
    honestly and leave TODOs rather than fabricate steps."""
    return (
        f"---\n"
        f"name: {cand_id}\n"
        f'description: Recurring workflow around "{fam.label}" '
        f"(seen in {fam.session_count} sessions). EDIT before approving.\n"
        f"---\n"
        f"# {fam.label}\n\n"
        f"<!-- WS draft mined from {fam.session_count} sessions"
        f"{f', {len(fam.projects)} projects' if fam.projects else ''}. "
        f"Replace the TODOs with the real reusable procedure, then `candidate approve`. -->\n\n"
        f"## When to use\n\n"
        f"TODO: the trigger you hit repeatedly.\n\n"
        f"## Steps\n\n"
        f"TODO: the procedure you re-derived each time.\n"
    )


class CandidateStore:
    """Filesystem store for draft candidates under ``<root>/candidates/<id>/``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or config.state_root()
        self.dir = self.root / "candidates"

    def _cdir(self, cand_id: str) -> Path:
        return self.dir / cand_id

    def get(self, cand_id: str) -> Candidate | None:
        meta = self._cdir(cand_id) / "candidate.json"
        if not meta.exists():
            return None
        try:
            return Candidate.model_validate_json(meta.read_text(encoding="utf-8"))
        except ValidationError as e:
            raise CandidateError(f"{cand_id}: corrupt candidate.json ({e})") from e

    def list(self) -> list[Candidate]:
        if not self.dir.exists():
            return []
        out = [self.get(d.name) for d in sorted(self.dir.iterdir()) if d.is_dir()]
        return [c for c in out if c is not None]

    def skill_md(self, cand_id: str) -> str:
        md = self._cdir(cand_id) / "SKILL.md"
        if not md.exists():
            raise CandidateError(f"candidate {cand_id!r} has no SKILL.md")
        return md.read_text(encoding="utf-8")

    def write_skill_md(self, cand_id: str, raw: str) -> None:
        self._cdir(cand_id).mkdir(parents=True, exist_ok=True)
        (self._cdir(cand_id) / "SKILL.md").write_text(raw, encoding="utf-8")

    def save(self, cand: Candidate) -> None:
        cdir = self._cdir(cand.candidate_id)
        cdir.mkdir(parents=True, exist_ok=True)
        # Atomic write so a crash can't leave a truncated candidate.json (M12).
        p = cdir / "candidate.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(cand.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)  # mined family labels are session-derived — not world-readable (P2-1)
        os.replace(tmp, p)


def draft_from_families(
    store: CandidateStore, families: list[OpportunityFamily]
) -> list[Candidate]:
    """Create one pending candidate per new family (idempotent by slug). Families
    whose label yields no legal slug are skipped."""
    created: list[Candidate] = []
    for fam in families:
        cand_id = slugify(fam.label)
        if not cand_id or store.get(cand_id) is not None:
            continue
        cand = Candidate(
            candidate_id=cand_id,
            family_label=fam.label,
            session_count=fam.session_count,
            event_count=fam.event_count,
            projects=sorted(fam.projects),
        )
        store.write_skill_md(cand_id, _draft_md(cand_id, fam))
        store.save(cand)
        created.append(cand)
    return created


def approve(
    store: CandidateStore,
    reg: Registry,
    cand_id: str,
    host_dir: Path,
    *,
    host_name: str | None = None,
    actor: str = "user",
    reason: str | None = None,
) -> SkillVersion:
    """Promote a candidate into the registry and materialize it to the host.

    The single write path (One Writer Rule): parses the current — possibly
    human-edited — SKILL.md, registers an immutable ACTIVE version, copies it to
    the host skills dir, and marks the candidate approved. Raises before any
    write if the candidate is unknown or already approved."""
    cand = store.get(cand_id)
    if cand is None:
        raise CandidateError(f"unknown candidate: {cand_id}")
    if cand.status == "approved":
        raise CandidateError(f"candidate {cand_id!r} already approved")

    raw = store.skill_md(cand_id)
    # Instruction-layer adversarial gate (docs/04 §2.4bis): v1's only mandatory
    # security gate. Runs BEFORE any write — a blocked candidate never reaches
    # the registry or the host. Captured content is untrusted; auto-approval
    # never bypasses this (there is no auto-approval, but the invariant holds).
    findings = scan_skill_md(raw)
    if findings:
        raise InstructionGateError(findings)
    # Quality gate (audit P2-2): a draft still carrying its TODO/"EDIT before
    # approving" scaffold is a hollow skill — block before promote so it can't
    # reach the host and route. Cheap deterministic check, before any write.
    if _has_template_placeholder(raw):
        raise CandidateError(
            f"candidate {cand_id!r} still has unedited draft placeholders "
            "(TODO / 'EDIT before approving') — edit SKILL.md before approving"
        )
    # Deterministic eval-lite hard gate (docs/04 §1.6): schema, zero secret leak,
    # token budget. The No Skill/Skill two-arm is Insufficient Evidence at WS.
    report = eval_lite(raw)
    if not report.passed:
        raise EvalError(report)
    skill_id = parse(raw).frontmatter.name  # frontmatter name is authoritative
    reg.init()
    prov = [
        Provenance(
            kind=ProvenanceKind.CAPTURED_SESSION,
            origin=f"mined:{cand.family_label} ({cand.session_count} sessions)",
        )
    ]
    sv = reg.add_version(
        skill_id,
        raw,
        CandidateType.CAPTURED,
        prov,
        status=SkillStatus.ACTIVE,
        actor=actor,
        reason=reason or f"approve candidate {cand_id}",
    )
    reg.materialize(skill_id, host_dir, host_name=host_name)

    cand.status = "approved"
    cand.skill_id = skill_id
    cand.version = sv.version
    store.save(cand)
    return sv


def reject(store: CandidateStore, cand_id: str) -> Candidate:
    cand = store.get(cand_id)
    if cand is None:
        raise CandidateError(f"unknown candidate: {cand_id}")
    cand.status = "rejected"
    store.save(cand)
    return cand

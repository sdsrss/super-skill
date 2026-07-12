"""Core data model — single source of truth (M0 deliverable).

Scoped to the v1 package manager. Fields the self-learning loop (M2-M5) needs
(ExperienceCard, CapabilityLedger, EvalRun, ...) are intentionally absent; they
land when/if the GATE opens the research track. Entity shapes here mirror
docs/02-architecture.md §5 so the M1 Registry/Publisher can adopt them unchanged.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# agentskills.io spec: name 1-64 chars, lowercase + hyphen, must match dir name.
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def utcnow() -> datetime:
    """Timezone-aware now(). Centralized so tests can monkeypatch one symbol."""
    return datetime.now(UTC)


class Scope(StrEnum):
    GLOBAL = "global"
    PROJECT = "project"


class CandidateType(StrEnum):
    """FR-GEN-3 six types. v1 seed/capture uses CAPTURED/FIX/DISTILLED."""

    FIX = "FIX"
    DERIVED = "DERIVED"
    CAPTURED = "CAPTURED"
    DISTILLED = "DISTILLED"
    CONSOLIDATED = "CONSOLIDATED"
    RETIRED = "RETIRED"


class SkillStatus(StrEnum):
    """Lifecycle states (docs/02 §6). v1/WS uses OBSERVED..ACTIVE minus the
    security-gate states (QUARANTINED/EVALUATED) that need M4 machinery."""

    OBSERVED = "Observed"
    CANDIDATE = "Candidate"
    QUARANTINED = "Quarantined"
    EVALUATED = "Evaluated"
    STAGED = "Staged"
    CANARY = "Canary"
    ACTIVE = "Active"
    REJECTED = "Rejected"
    RETIRED = "Retired"


class OperationType(StrEnum):
    """Writes that mutate the active skill set. In WS these are git commits;
    M1 wraps them in a signed OperationRecord verified by the Publisher."""

    PROMOTE = "PROMOTE"
    ROLLBACK = "ROLLBACK"
    REVOKE_CANARY = "REVOKE_CANARY"
    QUARANTINE = "QUARANTINE"
    RETIRE = "RETIRE"


class ProvenanceKind(StrEnum):
    SEED_EXISTING_SKILL = "seed_existing_skill"
    CAPTURED_SESSION = "captured_session"
    DISTILLED_EXTERNAL = "distilled_external"


class EventType(StrEnum):
    """The six host hook events captured in WS (docs/01 FR-CAP-1)."""

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"
    SESSION_END = "SessionEnd"


class RedactionMark(BaseModel):
    """What was redacted and where — never the value (docs/01 FR-CAP-2)."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    location: str = Field(description="dotted path of the field the secret was found in")
    count: int = 1


class CaptureEvent(BaseModel):
    """One redacted host event appended to the JSONL WAL. WS keeps only observable
    actions + short outcomes — never hidden chain-of-thought (FR-CAP-7)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    session_id: str
    event_type: EventType
    project_id: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)
    redactions: list[RedactionMark] = Field(default_factory=list)
    consent_scope: str = "default"


class Provenance(BaseModel):
    """Where a version's content came from and under what license."""

    model_config = ConfigDict(extra="forbid")

    kind: ProvenanceKind
    origin: str = Field(description="path, session id, or source URL")
    imported_at: datetime = Field(default_factory=utcnow)
    license: str | None = None
    notes: str | None = None


class SkillFrontmatter(BaseModel):
    """agentskills.io core frontmatter. Host-specific extensions are NOT held
    here — they are injected per-host at distribution time (docs/02 §4.2)."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _name_shape(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError(
                f"name must be lowercase alphanumerics + single hyphens (got {v!r})"
            )
        return v


class SkillVersion(BaseModel):
    """One immutable node in a skill's version DAG."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    version: str
    parent_versions: list[str] = Field(default_factory=list)
    candidate_type: CandidateType
    status: SkillStatus
    artifact_hash: str = Field(description="sha256 of the normalized SKILL.md payload")
    frontmatter: SkillFrontmatter
    provenance: list[Provenance] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Skill(BaseModel):
    """Skill-level state: the active-version pointer that rollback switches,
    distinct from the SkillVersion DAG nodes (docs/02 §5.1, review H4)."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    scope: Scope = Scope.GLOBAL
    active_version: str | None = None
    user_disabled: bool = False


class OperationRecord(BaseModel):
    """Record of an active-set mutation. WS fills actor/reason and relies on git
    for integrity; nonce/registry_state_hash/signature are added at M1 when the
    real Publisher exists (fields present-but-optional so the shape is stable)."""

    model_config = ConfigDict(extra="forbid")

    op: OperationType
    skill_id: str
    version: str | None = None
    rollback_version: str | None = None
    actor: str = "user"
    reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    # --- M1 (signed Publisher) ---
    nonce: str | None = None
    registry_state_hash: str | None = None
    signature: str | None = None


class AuditEvent(BaseModel):
    """Immutable audit trail entry. In WS these are reconstructable from git
    history; kept structured so `explain` renders a uniform provenance chain."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    op: OperationType
    from_version: str | None = None
    to_version: str | None = None
    actor: str = "user"
    reason: str | None = None
    artifact_hash: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

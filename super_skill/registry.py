"""Git-backed registry (WS backend).

Each skill is a directory under ``registry/skills/<skill_id>/`` holding immutable
``versions/<version>/SKILL.md`` snapshots plus a ``meta.json`` aggregate (Skill
pointer + SkillVersion DAG + audit trail). Git provides integrity, audit history
and rollback; M1 replaces this with the SQLite Registry + signed Publisher
without changing the entity shapes (docs/03 §3 M1, docs/02 §7.7).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from . import config
from .schemas import (
    AuditEvent,
    CandidateType,
    OperationType,
    Provenance,
    Scope,
    Skill,
    SkillStatus,
    SkillVersion,
)
from .skillmd import content_hash, parse

_GIT_ID = ["-c", "user.name=super-skill", "-c", "user.email=super-skill@localhost"]


class SkillRecord(BaseModel):
    """Per-skill aggregate persisted as meta.json."""

    model_config = ConfigDict(extra="forbid")

    skill: Skill
    versions: dict[str, SkillVersion] = Field(default_factory=dict)
    audit: list[AuditEvent] = Field(default_factory=list)

    @property
    def active(self) -> SkillVersion | None:
        v = self.skill.active_version
        return self.versions.get(v) if v else None

    def next_version(self) -> str:
        nums = [int(k.lstrip("v")) for k in self.versions if k.lstrip("v").isdigit()]
        return f"v{1 + max(nums, default=0)}"


class RegistryError(RuntimeError):
    pass


class Registry:
    """WS registry rooted at a state dir (injectable for tests)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or config.state_root()
        self.skills_root = self.root / "registry" / "skills"

    # ---- lifecycle ---------------------------------------------------------
    def init(self) -> None:
        self.skills_root.mkdir(parents=True, exist_ok=True)
        # candidates/ holds pre-promotion draft scratch — kept out of tracked
        # history so only approve (the Publisher path) writes registry state.
        gitignore = "locks/\ncandidates/\n"
        gi = self.root / ".gitignore"
        if not (self.root / ".git").exists():
            self._git("init", "-q")
            gi.write_text(gitignore, encoding="utf-8")
            self._commit("chore: initialize super-skill registry")
        elif gi.exists() and "candidates/" not in gi.read_text(encoding="utf-8"):
            gi.write_text(gitignore, encoding="utf-8")
            self._commit("chore: ignore candidates/ scratch dir")

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RegistryError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def _commit(self, message: str) -> str:
        self._git("add", "-A")
        # nothing staged is not an error (idempotent re-runs)
        status = self._git("status", "--porcelain")
        if not status:
            return self.head()
        subprocess.run(
            ["git", "-C", str(self.root), *_GIT_ID, "commit", "-q", "-m", message],
            capture_output=True,
            text=True,
            check=True,
        )
        return self.head()

    def head(self) -> str:
        try:
            return self._git("rev-parse", "--short", "HEAD")
        except RegistryError:
            return "(no commits)"

    # ---- reads -------------------------------------------------------------
    def _meta_path(self, skill_id: str) -> Path:
        return self.skills_root / skill_id / "meta.json"

    def get(self, skill_id: str) -> SkillRecord | None:
        p = self._meta_path(skill_id)
        if not p.exists():
            return None
        return SkillRecord.model_validate_json(p.read_text(encoding="utf-8"))

    def list_skills(self) -> list[SkillRecord]:
        if not self.skills_root.exists():
            return []
        out = [self.get(d.name) for d in sorted(self.skills_root.iterdir()) if d.is_dir()]
        return [r for r in out if r is not None]

    def version_text(self, skill_id: str, version: str) -> str:
        p = self.skills_root / skill_id / "versions" / version / "SKILL.md"
        if not p.exists():
            raise RegistryError(f"{skill_id}@{version} has no SKILL.md")
        return p.read_text(encoding="utf-8")

    # ---- writes ------------------------------------------------------------
    def add_version(
        self,
        skill_id: str,
        raw: str,
        candidate_type: CandidateType,
        provenance: list[Provenance],
        *,
        status: SkillStatus = SkillStatus.ACTIVE,
        scope: Scope = Scope.GLOBAL,
        make_active: bool = True,
        actor: str = "user",
        reason: str | None = None,
        commit: bool = True,
    ) -> SkillVersion:
        """Register a new immutable version; optionally make it the active pointer."""
        parsed = parse(raw)
        rec = self.get(skill_id) or SkillRecord(skill=Skill(skill_id=skill_id, scope=scope))
        version = rec.next_version()
        parents = [rec.skill.active_version] if rec.skill.active_version else []
        sv = SkillVersion(
            skill_id=skill_id,
            version=version,
            parent_versions=[p for p in parents if p],
            candidate_type=candidate_type,
            status=status,
            artifact_hash=content_hash(raw),
            frontmatter=parsed.frontmatter,
            provenance=provenance,
        )
        vdir = self.skills_root / skill_id / "versions" / version
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "SKILL.md").write_text(parsed.raw, encoding="utf-8")

        rec.versions[version] = sv
        prev = rec.skill.active_version
        if make_active:
            rec.skill.active_version = version
        rec.audit.append(
            AuditEvent(
                skill_id=skill_id,
                op=OperationType.PROMOTE,
                from_version=prev,
                to_version=version if make_active else prev,
                actor=actor,
                reason=reason,
                artifact_hash=sv.artifact_hash,
            )
        )
        self._write(rec)
        if commit:
            self._commit(f"promote: {skill_id}@{version} ({candidate_type})")
        return sv

    def set_active(
        self, skill_id: str, version: str, *, op: OperationType, actor: str = "user",
        reason: str | None = None, commit: bool = True,
    ) -> SkillRecord:
        """Switch the active-version pointer (rollback = point at an older version)."""
        rec = self.get(skill_id)
        if rec is None:
            raise RegistryError(f"unknown skill {skill_id!r}")
        if version not in rec.versions:
            raise RegistryError(f"{skill_id} has no version {version!r}")
        prev = rec.skill.active_version
        rec.skill.active_version = version
        rec.audit.append(
            AuditEvent(skill_id=skill_id, op=op, from_version=prev, to_version=version,
                       actor=actor, reason=reason)
        )
        self._write(rec)
        if commit:
            self._commit(f"{op.lower()}: {skill_id} -> {version}")
        return rec

    def _write(self, rec: SkillRecord) -> None:
        p = self._meta_path(rec.skill.skill_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rec.model_dump_json(indent=2), encoding="utf-8")

    # ---- distribution ------------------------------------------------------
    def materialize(self, skill_id: str, host_dir: Path) -> Path:
        """Write the active version's SKILL.md into the host skills dir so the
        Agent picks it up. Only writes that one file — never deletes siblings."""
        rec = self.get(skill_id)
        if rec is None or rec.skill.active_version is None:
            raise RegistryError(f"{skill_id!r} has no active version to materialize")
        raw = self.version_text(skill_id, rec.skill.active_version)
        dest = host_dir / skill_id / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(raw, encoding="utf-8")
        return dest

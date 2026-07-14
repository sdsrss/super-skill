"""Git-backed registry (WS backend).

Each skill is a directory under ``registry/skills/<skill_id>/`` holding immutable
``versions/<version>/SKILL.md`` snapshots plus a ``meta.json`` aggregate (Skill
pointer + SkillVersion DAG + audit trail). Git provides integrity, audit history
and rollback; M1 replaces this with the SQLite Registry + signed Publisher
without changing the entity shapes (docs/03 §3 M1, docs/02 §7.7).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config
from .schemas import (
    SCHEMA_VERSION,
    AuditEvent,
    CandidateType,
    OperationType,
    Provenance,
    Scope,
    Skill,
    SkillStatus,
    SkillVersion,
)

try:
    import fcntl  # POSIX-only advisory file locks
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]
from .skillmd import content_hash, parse

_GIT_ID = ["-c", "user.name=super-skill", "-c", "user.email=super-skill@localhost"]

# Untracked by the registry git backend: pre-promotion scratch (candidates/,
# locks/), the capture WAL + mine watermark + session-id cache (events/,
# mine_state.json, session_index.json — private session content that must not
# enter audit history, M9 / review F1), and atomic-write temps. init rewrites a
# stale .gitignore, so adding a line here self-heals existing registries.
_GITIGNORE = "locks/\ncandidates/\nevents/\nmine_state.json\nsession_index.json\n*.tmp\n"

# Everything super-skill itself may have placed in a state root. Used by the
# unborn-HEAD adoption check: any other entry means the directory is someone's
# working tree, not our state (review F2).
_OWN_ENTRIES = {
    ".git", ".gitignore", "registry", "locks", "events", "candidates",
    "mine_state.json", "session_index.json",
}


class SkillRecord(BaseModel):
    """Per-skill aggregate persisted as meta.json."""

    # extra="ignore" + schema_version: an older CLI reading a meta.json written by
    # a newer super-skill tolerates (drops) unknown fields instead of crashing
    # "corrupt meta.json"; the stamp lets a future reader detect version skew (N3).
    model_config = ConfigDict(extra="ignore")

    schema_version: int = SCHEMA_VERSION
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
        self._lock_depth = 0
        self._lock_fd: int | None = None

    # ---- cross-writer lock -------------------------------------------------
    @contextmanager
    def _lock(self) -> Iterator[None]:
        """Serialize the read-modify-write + git-commit critical section against
        another process/thread (audit P2-7 / P2-6). fcntl.flock on ``locks/``
        (git-ignored) via an exclusive advisory lock; re-entrant within one
        Registry instance so nested mutators (seed's batch add_version) don't
        deadlock. No-op where fcntl is unavailable (Windows) — the gitignore
        ``locks/`` entry is then a documented no-guarantee (residual risk).

        Invariant (review #1): a single ``Registry`` instance is scoped to one
        thread. Cross-thread/-process safety comes from *separate* instances each
        holding their own fd (as in the concurrency test and one-Registry-per-CLI
        -command usage). The re-entrancy accounting (``_lock_depth`` int, single
        ``_lock_fd``) is deliberately NOT guarded for a shared instance — sharing
        one instance across threads would race the counter and is unsupported."""
        if fcntl is None:  # pragma: no cover - non-POSIX
            yield
            return
        self._lock_depth += 1
        try:
            if self._lock_depth == 1:
                locks = self.root / "locks"
                locks.mkdir(parents=True, exist_ok=True)
                self._lock_fd = os.open(locks / "registry.lock", os.O_CREAT | os.O_RDWR, 0o600)
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            self._lock_depth -= 1
            if self._lock_depth == 0 and self._lock_fd is not None:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._lock_fd = None

    # ---- lifecycle ---------------------------------------------------------
    def init(self) -> None:
        with self._lock():  # serialize git-init + first commit against a concurrent init
            if (self.root / ".git").exists() and not self._owns_git_history():
                # Adopting a foreign repo would overwrite its .gitignore and
                # `git add -A` commit the user's working tree (audit P0-1).
                raise RegistryError(
                    f"refusing to adopt existing git repository at {self.root}: "
                    "its history was not created by super-skill. Point "
                    "SUPER_SKILL_HOME at a dedicated directory."
                )
            self.skills_root.mkdir(parents=True, exist_ok=True)
            if not (self.root / ".git").exists():
                self._git("init", "-q")
            gi = self.root / ".gitignore"
            # Rewrite whenever missing or stale — unconditionally, not gated on ``.git``
            # existing (a crash between ``git init`` and the first write, or a manual
            # ``git init``, used to leave it un-created and candidates/ tracked, M10).
            if not gi.exists() or gi.read_text(encoding="utf-8") != _GITIGNORE:
                gi.write_text(_GITIGNORE, encoding="utf-8")
            # Idempotent: no-op when nothing is staged (already-initialized re-run).
            self._commit("chore: initialize super-skill registry (.gitignore)")

    def _owns_git_history(self) -> bool:
        """True when the repo at root is empty (unborn HEAD) or its root commit
        was written by Registry.init — the only histories init may adopt."""
        try:
            roots = self._git("rev-list", "--max-parents=0", "HEAD")
        except RegistryError:
            # Unborn HEAD: fresh `git init`, but the WORKING TREE can still be
            # someone's un-committed directory — init would overwrite their
            # .gitignore (unrecoverable: never committed) and `git add -A`
            # their files (review F2). Adopt only when the tree holds nothing
            # but our own state and any .gitignore is already ours.
            foreign = [p.name for p in self.root.iterdir() if p.name not in _OWN_ENTRIES]
            if foreign:
                return False
            gi = self.root / ".gitignore"
            return not gi.exists() or gi.read_text(encoding="utf-8") == _GITIGNORE
        for commit in roots.splitlines():
            subject = self._git("log", "-1", "--format=%s", commit.strip())
            if subject.startswith("chore: initialize super-skill registry"):
                return True
        return False

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
        with self._lock():  # serialize git add/commit — no index.lock race (P2-6)
            return self._commit_locked(message)

    def _commit_locked(self, message: str) -> str:
        self._git("add", "-A")
        # nothing staged is not an error (idempotent re-runs)
        status = self._git("status", "--porcelain")
        if not status:
            return self.head()
        proc = subprocess.run(
            ["git", "-C", str(self.root), *_GIT_ID, "commit", "-q", "-m", message],
            capture_output=True,
            text=True,
        )
        # Surface a failed commit as RegistryError (which the CLI catches) instead
        # of a raw CalledProcessError traceback (L15).
        if proc.returncode != 0:
            raise RegistryError(f"git commit failed: {proc.stderr.strip()}")
        return self.head()

    def head(self) -> str:
        try:
            return self._git("rev-parse", "--short", "HEAD")
        except RegistryError:
            return "(no commits)"

    # Public API for sibling modules (seed/doctor) — avoids reaching into the
    # private _git/_commit across module boundaries (P3-5).
    def git(self, *args: str) -> str:
        """Run a git subcommand in the registry repo; raises RegistryError on failure."""
        return self._git(*args)

    def commit(self, message: str) -> str:
        """Commit staged registry changes (no-op when nothing is staged)."""
        return self._commit(message)

    # ---- reads -------------------------------------------------------------
    def _meta_path(self, skill_id: str) -> Path:
        return self.skills_root / skill_id / "meta.json"

    def get(self, skill_id: str) -> SkillRecord | None:
        p = self._meta_path(skill_id)
        if not p.exists():
            return None
        try:
            return SkillRecord.model_validate_json(p.read_text(encoding="utf-8"))
        except ValidationError as e:
            # A truncated/corrupt meta.json (crash mid-write, hand-edit) must
            # surface as RegistryError so status/list/doctor report it cleanly
            # rather than dying on a raw pydantic traceback (M12).
            raise RegistryError(f"{skill_id}: corrupt meta.json ({e})") from e

    def list_skills(
        self, on_error: Callable[[str, RegistryError], None] | None = None
    ) -> list[SkillRecord]:
        """All readable skill records. A corrupt meta.json raises (strict) unless
        ``on_error`` is given, in which case the skill is skipped and reported —
        read-only surfaces (status/list/doctor) must degrade per-skill instead of
        dying wholesale on one bad file (audit P1-5)."""
        if not self.skills_root.exists():
            return []
        out: list[SkillRecord] = []
        for d in sorted(self.skills_root.iterdir()):
            if not d.is_dir():
                continue
            try:
                rec = self.get(d.name)
            except RegistryError as e:
                if on_error is None:
                    raise
                on_error(d.name, e)
                continue
            if rec is not None:
                out.append(rec)
        return out

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
        # Hold the cross-writer lock across the whole read-modify-write so a
        # concurrent promotion of the same skill can't clobber this one (P2-6).
        with self._lock():
            rec = self.get(skill_id) or SkillRecord(skill=Skill(skill_id=skill_id, scope=scope))
            # Idempotent promotion (M8): re-adding content identical to the current
            # active version is a no-op. Guards the approve crash window (candidate
            # left 'pending' after commit) from double-promoting on re-run.
            new_hash = content_hash(raw)
            if make_active and rec.skill.active_version:
                cur = rec.versions.get(rec.skill.active_version)
                if cur is not None and cur.artifact_hash == new_hash:
                    return cur
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
        with self._lock():  # read-modify-write under the cross-writer lock (P2-6)
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
        # Atomic write: a crash mid-write must never leave a truncated meta.json
        # (M12). Write to a sibling temp file, then os.replace (atomic rename).
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(rec.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)  # session-derived provenance/audit — not world-readable (P2-1)
        os.replace(tmp, p)

    # ---- distribution ------------------------------------------------------
    def materialize(self, skill_id: str, host_dir: Path, *, host_name: str | None = None) -> Path:
        """Write the active version's SKILL.md into the host skills dir so the
        Agent picks it up. Only writes that one file — never deletes siblings.

        When ``host_name`` is given, record it in the skill's ``materialized_hosts``
        so rollback/doctor re-sync/verify every host it was pushed to, not just the
        default claude one (P2-5). The tracking write is under the cross-writer lock."""
        with self._lock():
            rec = self.get(skill_id)
            if rec is None or rec.skill.active_version is None:
                raise RegistryError(f"{skill_id!r} has no active version to materialize")
            raw = self.version_text(skill_id, rec.skill.active_version)
            dest = host_dir / skill_id / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(raw, encoding="utf-8")
            if host_name is not None and host_name not in rec.skill.materialized_hosts:
                rec.skill.materialized_hosts = sorted({*rec.skill.materialized_hosts, host_name})
                self._write(rec)
                self._commit(f"materialize: {skill_id} -> {host_name}")
            return dest

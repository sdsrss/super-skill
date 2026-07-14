"""Registry integrity self-check and repair (`super-skill doctor [--fix]`).

`check_registry` is read-only: it verifies the WS registry is internally
consistent and, when a host dir is given, in sync with it. The highest-value
check is content-hash integrity — a version's on-disk SKILL.md must still hash to
the `artifact_hash` recorded when it was promoted, catching tampering,
corruption, or a hand-edit that bypassed the registry.

`repair` fixes the mechanically-fixable issues: git is the WS backend, so a
tampered/missing version file is restored from HEAD (which holds the committed,
correct content), and host drift is re-materialized from the active version.
Issues that need judgment (a dangling active pointer, a name mismatch) are left
for the user. Repair always re-verifies afterwards and reports what actually
remains — an attempted fix is not a fix (see the doctor exit-code lesson).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import config
from .registry import Registry, RegistryError
from .skillmd import content_hash


@dataclass(frozen=True)
class DoctorIssue:
    skill_id: str
    severity: str  # "error" (integrity broken) | "warn" (drift / cosmetic)
    message: str
    kind: str = ""  # machine-dispatchable: see check_registry
    version: str | None = None
    host: str | None = None  # host-scoped issues (host_missing / host_drift), P2-5


def check_registry(
    reg: Registry,
    host_dir: Path | None = None,
    *,
    resolve_host: Callable[[str], Path] | None = None,
) -> list[DoctorIssue]:
    """Verify registry integrity and, per skill, host sync for every host the skill
    was materialized to (``materialized_hosts``, P2-5). ``resolve_host`` maps a host
    name to its skills dir (defaults to config; injectable for tests). ``host_dir``
    is the legacy single-host fallback used only for skills with no recorded hosts."""
    resolve_host = resolve_host or config.host_skills_dir
    issues: list[DoctorIssue] = []
    # A corrupt meta.json must become a reportable (and git-repairable) issue,
    # not crash the integrity tool on the exact corruption it exists to
    # diagnose (audit P1-5).
    records = reg.list_skills(
        on_error=lambda sid, e: issues.append(
            DoctorIssue(sid, "error", f"corrupt meta.json ({e})", kind="meta_corrupt")
        )
    )
    for rec in records:
        sid = rec.skill.skill_id
        active = rec.skill.active_version

        if active is not None and active not in rec.versions:
            have = ", ".join(rec.versions) or "none"
            issues.append(
                DoctorIssue(
                    sid, "error",
                    f"active pointer {active!r} not in versions (have: {have}) — "
                    f"fix with `super-skill rollback {sid} --to <version>`",
                    kind="dangling_active",
                )
            )

        for ver, sv in rec.versions.items():
            try:
                raw = reg.version_text(sid, ver)
            except RegistryError:
                issues.append(
                    DoctorIssue(sid, "error", f"{ver}: SKILL.md file missing",
                                kind="file_missing", version=ver)
                )
                continue
            if content_hash(raw) != sv.artifact_hash:
                issues.append(
                    DoctorIssue(sid, "error", f"{ver}: content hash mismatch (tampered/corrupt)",
                                kind="hash_mismatch", version=ver)
                )
            if sv.frontmatter.name != sid:
                issues.append(
                    DoctorIssue(sid, "warn",
                                f"{ver}: frontmatter name {sv.frontmatter.name!r} != skill_id",
                                kind="name_mismatch", version=ver)
                )

        if active is not None and active in rec.versions:
            # Check every host the skill was materialized to (P2-5). Legacy skills
            # with no recorded hosts fall back to the single host_dir (label None).
            tracked = rec.skill.materialized_hosts
            if tracked:
                pairs: list[tuple[str | None, Path]] = [(h, resolve_host(h)) for h in tracked]
            elif host_dir is not None:
                pairs = [(None, host_dir)]
            else:
                pairs = []
            for host_label, hdir in pairs:
                suffix = f" {host_label}" if host_label else ""
                host_md = hdir / sid / "SKILL.md"
                if not host_md.exists():
                    issues.append(
                        DoctorIssue(sid, "warn", f"active version not materialized to host{suffix}",
                                    kind="host_missing", host=host_label)
                    )
                elif content_hash(host_md.read_text(encoding="utf-8")) != content_hash(
                    reg.version_text(sid, active)
                ):
                    issues.append(
                        DoctorIssue(sid, "warn",
                                    f"host{suffix} SKILL.md differs from active version "
                                    "(edited/stale)", kind="host_drift", host=host_label)
                    )

    return issues


@dataclass(frozen=True)
class RepairAction:
    issue: DoctorIssue
    action: str  # what was attempted
    ok: bool


def repair(
    reg: Registry,
    host_dir: Path | None = None,
    *,
    resolve_host: Callable[[str], Path] | None = None,
) -> tuple[list[RepairAction], list[DoctorIssue]]:
    """Fix the mechanically-fixable issues, then RE-VERIFY.

    Returns (actions attempted, issues still present after re-check). The caller
    decides exit status from the *remaining* issues, never from attempts."""
    resolve_host = resolve_host or config.host_skills_dir
    actions: list[RepairAction] = []
    for issue in check_registry(reg, host_dir, resolve_host=resolve_host):
        if issue.kind in ("hash_mismatch", "file_missing") and issue.version is not None:
            rel = f"registry/skills/{issue.skill_id}/versions/{issue.version}/SKILL.md"
            try:
                reg.git("checkout", "HEAD", "--", rel)
                actions.append(RepairAction(issue, f"restored {rel} from git HEAD", True))
            except RegistryError as e:
                actions.append(RepairAction(issue, f"git restore failed: {e}", False))
        elif issue.kind == "meta_corrupt":
            # meta.json is committed on every registry write — git HEAD holds
            # the last good copy (audit P1-5).
            rel = f"registry/skills/{issue.skill_id}/meta.json"
            try:
                reg.git("checkout", "HEAD", "--", rel)
                actions.append(RepairAction(issue, f"restored {rel} from git HEAD", True))
            except RegistryError as e:
                actions.append(RepairAction(issue, f"git restore failed: {e}", False))
        elif issue.kind in ("host_missing", "host_drift"):
            # Re-materialize to the SPECIFIC drifted host (P2-5), not just claude.
            hdir = resolve_host(issue.host) if issue.host else host_dir
            if hdir is None:
                continue
            try:
                reg.materialize(issue.skill_id, hdir, host_name=issue.host)
                where = f" ({issue.host})" if issue.host else ""
                actions.append(
                    RepairAction(issue, f"re-materialized active version to host{where}", True)
                )
            except RegistryError as e:
                actions.append(RepairAction(issue, f"materialize failed: {e}", False))
        # dangling_active / name_mismatch need judgment — left for the user.

    remaining = check_registry(reg, host_dir, resolve_host=resolve_host)
    return actions, remaining

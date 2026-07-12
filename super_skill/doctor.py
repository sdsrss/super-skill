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

from dataclasses import dataclass
from pathlib import Path

from .registry import Registry, RegistryError
from .skillmd import content_hash


@dataclass(frozen=True)
class DoctorIssue:
    skill_id: str
    severity: str  # "error" (integrity broken) | "warn" (drift / cosmetic)
    message: str
    kind: str = ""  # machine-dispatchable: see check_registry
    version: str | None = None


def check_registry(reg: Registry, host_dir: Path | None = None) -> list[DoctorIssue]:
    issues: list[DoctorIssue] = []
    for rec in reg.list_skills():
        sid = rec.skill.skill_id
        active = rec.skill.active_version

        if active is not None and active not in rec.versions:
            issues.append(
                DoctorIssue(sid, "error", f"active pointer {active!r} not in versions",
                            kind="dangling_active")
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

        if host_dir is not None and active is not None and active in rec.versions:
            host_md = host_dir / sid / "SKILL.md"
            if not host_md.exists():
                issues.append(
                    DoctorIssue(sid, "warn", "active version not materialized to host",
                                kind="host_missing")
                )
            elif content_hash(host_md.read_text(encoding="utf-8")) != content_hash(
                reg.version_text(sid, active)
            ):
                issues.append(
                    DoctorIssue(sid, "warn",
                                "host SKILL.md differs from active version (edited/stale)",
                                kind="host_drift")
                )

    return issues


@dataclass(frozen=True)
class RepairAction:
    issue: DoctorIssue
    action: str  # what was attempted
    ok: bool


def repair(
    reg: Registry, host_dir: Path | None = None
) -> tuple[list[RepairAction], list[DoctorIssue]]:
    """Fix the mechanically-fixable issues, then RE-VERIFY.

    Returns (actions attempted, issues still present after re-check). The caller
    decides exit status from the *remaining* issues, never from attempts."""
    actions: list[RepairAction] = []
    for issue in check_registry(reg, host_dir):
        if issue.kind in ("hash_mismatch", "file_missing") and issue.version is not None:
            rel = f"registry/skills/{issue.skill_id}/versions/{issue.version}/SKILL.md"
            try:
                reg._git("checkout", "HEAD", "--", rel)
                actions.append(RepairAction(issue, f"restored {rel} from git HEAD", True))
            except RegistryError as e:
                actions.append(RepairAction(issue, f"git restore failed: {e}", False))
        elif issue.kind in ("host_missing", "host_drift") and host_dir is not None:
            try:
                reg.materialize(issue.skill_id, host_dir)
                actions.append(RepairAction(issue, "re-materialized active version to host", True))
            except RegistryError as e:
                actions.append(RepairAction(issue, f"materialize failed: {e}", False))
        # dangling_active / name_mismatch need judgment — left for the user.

    remaining = check_registry(reg, host_dir)
    return actions, remaining

"""Registry integrity self-check (`super-skill doctor`).

Read-only: it verifies the WS registry is internally consistent and, when a host
dir is given, in sync with it — but never mutates state. Remediation is the
user's call via `rollback` / `seed` / re-materialize. Because git is the WS
backend, the highest-value check is content-hash integrity: a version's on-disk
SKILL.md must still hash to the `artifact_hash` recorded when it was promoted,
which catches tampering, corruption, or a hand-edit that bypassed the registry.
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


def check_registry(reg: Registry, host_dir: Path | None = None) -> list[DoctorIssue]:
    issues: list[DoctorIssue] = []
    for rec in reg.list_skills():
        sid = rec.skill.skill_id
        active = rec.skill.active_version

        if active is not None and active not in rec.versions:
            issues.append(DoctorIssue(sid, "error", f"active pointer {active!r} not in versions"))

        for ver, sv in rec.versions.items():
            try:
                raw = reg.version_text(sid, ver)
            except RegistryError:
                issues.append(DoctorIssue(sid, "error", f"{ver}: SKILL.md file missing"))
                continue
            if content_hash(raw) != sv.artifact_hash:
                issues.append(
                    DoctorIssue(sid, "error", f"{ver}: content hash mismatch (tampered/corrupt)")
                )
            if sv.frontmatter.name != sid:
                issues.append(
                    DoctorIssue(
                        sid, "warn", f"{ver}: frontmatter name {sv.frontmatter.name!r} != skill_id"
                    )
                )

        if host_dir is not None and active is not None and active in rec.versions:
            host_md = host_dir / sid / "SKILL.md"
            if not host_md.exists():
                issues.append(DoctorIssue(sid, "warn", "active version not materialized to host"))
            elif content_hash(host_md.read_text(encoding="utf-8")) != content_hash(
                reg.version_text(sid, active)
            ):
                issues.append(
                    DoctorIssue(
                        sid, "warn", "host SKILL.md differs from active version (edited/stale)"
                    )
                )

    return issues

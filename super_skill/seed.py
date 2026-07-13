"""Seed mode (docs/03 M0, D-3): ingest existing host skills into the registry so
explain/rollback/list have day-1 value with zero authoring.

Read-only with respect to the host skills directory — it reads each SKILL.md and
writes only into the registry. Idempotent: unchanged skills are skipped, changed
ones get a new version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .registry import Registry
from .schemas import CandidateType, Provenance, ProvenanceKind, SkillStatus
from .skillmd import SkillMdError, content_hash, parse


@dataclass
class SeedReport:
    imported: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)

    @property
    def total_seen(self) -> int:
        return len(self.imported) + len(self.updated) + len(self.unchanged) + len(self.skipped)


def seed_from_host(reg: Registry, host_dir: Path) -> SeedReport:
    report = SeedReport()
    reg.init()
    if not host_dir.exists():
        return report

    for d in sorted(p for p in host_dir.iterdir() if p.is_dir()):
        md = d / "SKILL.md"
        if not md.exists():
            report.skipped.append((d.name, "no SKILL.md"))
            continue
        raw = md.read_text(encoding="utf-8")
        try:
            parsed = parse(raw)
        except SkillMdError as e:
            report.skipped.append((d.name, str(e)))
            continue

        skill_id = parsed.frontmatter.name
        # agentskills.io: frontmatter name must match the dir name. If it doesn't,
        # skip rather than silently versioning one skill under another's id — two
        # dirs sharing a name would otherwise collapse into one version chain (M11).
        if skill_id != d.name:
            report.skipped.append((d.name, f"frontmatter name {skill_id!r} != dir name"))
            continue
        existing = reg.get(skill_id)
        if (
            existing is not None
            and existing.active is not None
            and existing.active.artifact_hash == content_hash(raw)
        ):
            report.unchanged.append(skill_id)
            continue

        prov = [Provenance(kind=ProvenanceKind.SEED_EXISTING_SKILL, origin=str(md))]
        reg.add_version(
            skill_id,
            raw,
            CandidateType.DISTILLED,
            prov,
            status=SkillStatus.ACTIVE,
            actor="seed",
            reason=f"seed import from {md}",
            commit=False,
        )
        (report.updated if existing else report.imported).append(skill_id)

    reg.commit(
        f"seed: import {len(report.imported)} new / {len(report.updated)} updated from host"
    )
    return report

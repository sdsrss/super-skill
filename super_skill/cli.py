"""super-skill CLI (WS P0 subset, docs/01 FR-IF-1): seed / status / list / show /
explain / rollback. The self-learning commands (sleep, distill, candidate-eval)
arrive only if the GATE opens the M2-M5 research track."""

from __future__ import annotations

import json
import sys

import typer

from . import config
from .candidate import CandidateError, CandidateStore, approve, draft_from_families, reject
from .capture import EventLog
from .mine import mine_families
from .registry import Registry, RegistryError
from .schemas import EventType, OperationType
from .seed import seed_from_host
from .skillmd import SkillMdError

app = typer.Typer(add_completion=False, help="Personal Agent-Skill package manager.")
candidate_app = typer.Typer(help="Draft / review / approve skill candidates (mine -> approve).")
app.add_typer(candidate_app, name="candidate")


def _registry() -> Registry:
    return Registry(root=config.state_root())


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


@app.command()
def seed() -> None:
    """Import existing host skills into the registry (idempotent, read-only on host)."""
    reg = _registry()
    report = seed_from_host(reg, config.host_skills_dir())
    typer.echo(
        f"seed: {len(report.imported)} imported, {len(report.updated)} updated, "
        f"{len(report.unchanged)} unchanged, {len(report.skipped)} skipped "
        f"(host={config.host_skills_dir()})"
    )
    for name, reason in report.skipped:
        typer.echo(f"  skipped {name}: {reason}")


@app.command()
def capture(
    event_type: str = typer.Option("", "--event-type", help="override hook_event_name"),
) -> None:
    """Append a host hook event (JSON on stdin) to the WAL, redacted.

    Designed to be called from a Claude Code hook. Never fails the session
    (NFR-3): malformed input or an unknown event type exits 0 without writing.
    """
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        raise typer.Exit(0) from None
    name = event_type or str(data.get("hook_event_name", ""))
    try:
        etype = EventType(name)
    except ValueError:
        raise typer.Exit(0) from None
    session_id = str(data.get("session_id", "unknown"))
    project_id = data.get("cwd")
    EventLog().append(
        etype, session_id, data, project_id=str(project_id) if project_id else None
    )


@app.command()
def mine(min_sessions: int = typer.Option(3, "--min-sessions")) -> None:
    """Surface recurring task families from captured events (FR-GEN-1 signal)."""
    families = mine_families(EventLog().iter_events(), min_sessions=min_sessions)
    if not families:
        typer.echo(f"no families recurring across >={min_sessions} sessions yet")
        return
    typer.echo(f"{'sessions':>8}  {'events':>6}  family")
    for fam in families:
        typer.echo(f"{fam.session_count:>8}  {fam.event_count:>6}  {fam.label}")


@app.command()
def status() -> None:
    """Registry summary: location, git head, skill/version counts."""
    reg = _registry()
    records = reg.list_skills()
    active = sum(1 for r in records if r.skill.active_version)
    versions = sum(len(r.versions) for r in records)
    typer.echo(f"state root : {reg.root}")
    typer.echo(f"git head   : {reg.head()}")
    typer.echo(f"skills     : {len(records)} ({active} active)")
    typer.echo(f"versions   : {versions}")
    typer.echo(f"events     : {EventLog(reg.root).count()}")


@app.command("list")
def list_() -> None:
    """List registered skills with their active version and description."""
    reg = _registry()
    records = reg.list_skills()
    if not records:
        typer.echo("no skills registered — run `super-skill seed`")
        return
    for r in records:
        av = r.active
        ver = r.skill.active_version or "-"
        desc = _short(av.frontmatter.description) if av else ""
        typer.echo(f"{r.skill.skill_id:<32} {ver:<5} {desc}")


@app.command()
def show(skill_id: str) -> None:
    """Show a skill's frontmatter, version history and provenance."""
    reg = _registry()
    rec = reg.get(skill_id)
    if rec is None:
        typer.echo(f"unknown skill: {skill_id}", err=True)
        raise typer.Exit(1)
    av = rec.active
    typer.echo(f"skill      : {rec.skill.skill_id} (scope={rec.skill.scope})")
    typer.echo(f"active     : {rec.skill.active_version}")
    if av:
        typer.echo(f"description: {av.frontmatter.description}")
        typer.echo(f"hash       : {av.artifact_hash}")
    typer.echo("versions   :")
    for ver, sv in rec.versions.items():
        mark = "*" if ver == rec.skill.active_version else " "
        typer.echo(f"  {mark} {ver:<5} {sv.candidate_type:<11} {sv.status}")


@app.command()
def explain(skill_id: str) -> None:
    """FR-IF-5: why this skill exists, where it came from, and how to roll it back."""
    reg = _registry()
    rec = reg.get(skill_id)
    if rec is None:
        typer.echo(f"unknown skill: {skill_id}", err=True)
        raise typer.Exit(1)
    typer.echo(f"# {rec.skill.skill_id}")
    for sv in rec.versions.values():
        origins = ", ".join(f"{p.kind}:{p.origin}" for p in sv.provenance) or "(none)"
        typer.echo(f"{sv.version} [{sv.candidate_type}] from {origins}")
    typer.echo("\naudit:")
    for ev in rec.audit:
        detail = f" ({ev.reason})" if ev.reason else ""
        typer.echo(f"  {ev.created_at:%Y-%m-%d %H:%M} {ev.op} {ev.from_version}->{ev.to_version}"
                   f" by {ev.actor}{detail}")
    versions = list(rec.versions)
    active = rec.skill.active_version
    if active and versions.index(active) > 0:
        prev = versions[versions.index(active) - 1]
        typer.echo(f"\nrollback : super-skill rollback {skill_id} --to {prev}")


@app.command()
def rollback(
    skill_id: str,
    to: str = typer.Option("", "--to", help="target version; default = previous"),
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Switch the active pointer to an older version and re-materialize to the host."""
    reg = _registry()
    rec = reg.get(skill_id)
    if rec is None:
        typer.echo(f"unknown skill: {skill_id}", err=True)
        raise typer.Exit(1)
    versions = list(rec.versions)
    if not to:
        idx = versions.index(rec.skill.active_version) if rec.skill.active_version else 0
        if idx <= 0:
            typer.echo("no previous version to roll back to", err=True)
            raise typer.Exit(1)
        to = versions[idx - 1]
    try:
        reg.set_active(skill_id, to, op=OperationType.ROLLBACK, reason=reason or None)
        dest = reg.materialize(skill_id, config.host_skills_dir())
    except RegistryError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"rolled back {skill_id} -> {to}; materialized {dest}")


@candidate_app.command("draft")
def candidate_draft(min_sessions: int = typer.Option(3, "--min-sessions")) -> None:
    """Draft skill candidates from mined families (idempotent, pre-promotion)."""
    families = mine_families(EventLog().iter_events(), min_sessions=min_sessions)
    store = CandidateStore(config.state_root())
    created = draft_from_families(store, families)
    if not created:
        typer.echo("no new candidates (nothing mined, or all already drafted)")
        return
    typer.echo(f"drafted {len(created)} candidate(s):")
    for c in created:
        typer.echo(f"  {c.candidate_id:<32} {c.session_count} sessions — edit then approve")


@candidate_app.command("list")
def candidate_list() -> None:
    """List drafted candidates and their status."""
    cands = CandidateStore(config.state_root()).list()
    if not cands:
        typer.echo("no candidates — run `super-skill candidate draft`")
        return
    for c in cands:
        typer.echo(
            f"{c.candidate_id:<32} {c.status:<9} "
            f"{c.session_count} sessions  {c.family_label}"
        )


@candidate_app.command("show")
def candidate_show(candidate_id: str) -> None:
    """Show a candidate's metadata and drafted SKILL.md."""
    store = CandidateStore(config.state_root())
    cand = store.get(candidate_id)
    if cand is None:
        typer.echo(f"unknown candidate: {candidate_id}", err=True)
        raise typer.Exit(1)
    typer.echo(f"candidate  : {cand.candidate_id} ({cand.status})")
    typer.echo(f"family     : {cand.family_label}")
    typer.echo(f"recurrence : {cand.session_count} sessions, {cand.event_count} events")
    if cand.version:
        typer.echo(f"promoted   : {cand.skill_id}@{cand.version}")
    typer.echo("--- SKILL.md ---")
    typer.echo(store.skill_md(candidate_id))


@candidate_app.command("approve")
def candidate_approve(
    candidate_id: str,
    reason: str = typer.Option("", "--reason"),
) -> None:
    """Approve a candidate: promote to the registry and materialize to the host."""
    store = CandidateStore(config.state_root())
    reg = _registry()
    try:
        sv = approve(store, reg, candidate_id, config.host_skills_dir(), reason=reason or None)
    except (CandidateError, RegistryError, SkillMdError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(
        f"approved {candidate_id} -> {sv.skill_id}@{sv.version}; "
        f"materialized to {config.host_skills_dir() / sv.skill_id}"
    )


@candidate_app.command("reject")
def candidate_reject(candidate_id: str) -> None:
    """Mark a candidate rejected (leaves it on disk for the record)."""
    store = CandidateStore(config.state_root())
    try:
        reject(store, candidate_id)
    except CandidateError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"rejected {candidate_id}")


if __name__ == "__main__":
    app()

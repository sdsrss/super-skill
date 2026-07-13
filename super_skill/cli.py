"""super-skill CLI (WS P0 subset, docs/01 FR-IF-1): seed / status / list / show /
explain / rollback. The self-learning commands (sleep, distill, candidate-eval)
arrive only if the GATE opens the M2-M5 research track."""

from __future__ import annotations

import json
import os
import sys

import typer

from . import config, hooks, minestate
from .candidate import CandidateError, CandidateStore, approve, draft_from_families, reject
from .capture import DEFAULT_EVENT_TTL_DAYS, EventLog
from .doctor import check_registry, repair
from .evallite import EvalError, eval_lite
from .gate import InstructionGateError, scan_skill_md
from .hooks import hooks_settings
from .mine import mine_families
from .registry import Registry, RegistryError
from .schemas import NAME_RE, EventType, OperationType
from .seed import seed_from_host
from .skillmd import SkillMdError

app = typer.Typer(add_completion=False, help="Personal Agent-Skill package manager.")
candidate_app = typer.Typer(help="Draft / review / approve skill candidates (mine -> approve).")
app.add_typer(candidate_app, name="candidate")


def _registry() -> Registry:
    return Registry(root=config.state_root())


def _require_valid_name(value: str, kind: str = "skill id") -> None:
    """Reject a user-supplied id that isn't an agentskills.io-legal name before it
    reaches a filesystem path — a ``../`` id would otherwise let a command traverse
    outside the registry/candidates dir (self-harm, but still, audit L19 + review #2)."""
    if not NAME_RE.match(value):
        typer.echo(
            f"invalid {kind} {value!r} (expected lowercase alphanumerics + single hyphens)",
            err=True,
        )
        raise typer.Exit(1)


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


@app.command()
def seed(host: str = typer.Option("claude", "--host", help="source host: claude | codex")) -> None:
    """Import existing host skills into the registry (idempotent, read-only on host)."""
    if host not in config.HOSTS:
        typer.echo(f"unknown host {host!r} (expected: {', '.join(config.HOSTS)})", err=True)
        raise typer.Exit(1)
    reg = _registry()
    src = config.host_skills_dir(host)
    report = seed_from_host(reg, src)
    typer.echo(
        f"seed: {len(report.imported)} imported, {len(report.updated)} updated, "
        f"{len(report.unchanged)} unchanged, {len(report.skipped)} skipped "
        f"(host={src})"
    )
    for name, reason in report.skipped:
        typer.echo(f"  skipped {name}: {reason}")


@app.command()
def materialize(
    skill_id: str = typer.Argument("", help="skill to distribute; empty = all active skills"),
    host: str = typer.Option("claude", "--host", help="target host: claude | codex | all"),
) -> None:
    """Distribute active skill(s) to a host skills dir — Claude Code and/or Codex (FR-PUB-2)."""
    if skill_id:
        _require_valid_name(skill_id)
    reg = _registry()
    try:
        hosts = config.resolve_hosts(host)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    ids = [skill_id] if skill_id else [
        r.skill.skill_id for r in reg.list_skills() if r.skill.active_version
    ]
    if not ids:
        typer.echo("no active skills to materialize")
        return
    failed = False
    for sid in ids:
        for h in hosts:
            try:
                dest = reg.materialize(sid, config.host_skills_dir(h), host_name=h)
                typer.echo(f"{sid} -> {h}: {dest}")
            except RegistryError as e:
                typer.echo(f"{sid} -> {h}: {e}", err=True)
                failed = True
    if failed:
        raise typer.Exit(1)


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
    except Exception:
        # NFR-3: never fail the session. Covers JSONDecodeError, OSError, and
        # RecursionError (deeply-nested JSON — a RuntimeError, not JSONDecodeError).
        raise typer.Exit(0) from None
    # NFR-3: the hook must NEVER fail the host session. Everything past here —
    # non-dict JSON (data.get would raise), an unknown event type, or any WAL
    # write error — is swallowed and exits 0. Capture-never-fails beats
    # capture-complete.
    try:
        if not isinstance(data, dict):
            raise typer.Exit(0)
        name = event_type or str(data.get("hook_event_name", ""))
        etype = EventType(name)  # ValueError on unknown type
        session_id = str(data.get("session_id", "unknown"))
        project_id = data.get("cwd")
        EventLog().append(
            etype, session_id, data, project_id=str(project_id) if project_id else None
        )
    except typer.Exit:
        raise
    except Exception:
        raise typer.Exit(0) from None


@app.command()
def mine(min_sessions: int = typer.Option(3, "--min-sessions")) -> None:
    """Surface recurring task families from captured events (FR-GEN-1 signal)."""
    log = EventLog()
    session_ids = log.session_ids()
    families = mine_families(log.iter_events(), min_sessions=min_sessions)
    # Acknowledge BEFORE printing: `mine | head` dies of SIGPIPE mid-listing,
    # and the watermark write must survive the broken pipe (D#67).
    minestate.record_mined(log.root, session_ids)
    if not families:
        typer.echo(
            f"no families recurring across >={min_sessions} sessions yet "
            f"({len(session_ids)} distinct sessions captured)"
        )
    else:
        typer.echo(f"{'sessions':>8}  {'events':>6}  family")
        for fam in families:
            typer.echo(f"{fam.session_count:>8}  {fam.event_count:>6}  {fam.label}")
    _mine_disk_footer(log)


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{n} B"
        size /= 1024
    return f"{size:.1f} GB"


def _event_ttl_days() -> int:
    """SUPER_SKILL_EVENT_TTL, shared by the mine footer and `prune` so the
    footer can never recommend a command that would then reject the same env.
    Invalid or negative values warn and fall back to the default."""
    raw = os.environ.get("SUPER_SKILL_EVENT_TTL")
    if not raw:
        return DEFAULT_EVENT_TTL_DAYS
    try:
        ttl = int(raw)
        if ttl < 0:
            raise ValueError
        return ttl
    except ValueError:
        typer.echo(
            f"ignoring invalid SUPER_SKILL_EVENT_TTL={raw!r}; "
            f"using default {DEFAULT_EVENT_TTL_DAYS}",
            err=True,
        )
        return DEFAULT_EVENT_TTL_DAYS


def _mine_disk_footer(log: EventLog) -> None:
    """Post-mine WAL-footprint nudge (FR-CAP-6). mine is the natural moment the
    user looks at captured data, so report its disk cost and — when day dirs have
    aged past the TTL — the reclaim command. Read-only: dry-run prune, no delete.
    stderr, so `mine | head`-style piping of the family table is unaffected."""
    total, days = log.disk_usage()
    if days == 0:
        return
    ttl = _event_ttl_days()
    stale = log.prune(days=ttl)  # dry-run: names prunable days, deletes nothing
    line = f"events on disk: {_human_size(total)} across {days} day(s); "
    if stale:
        line += (
            f"{len(stale)} day(s) beyond the {ttl}-day TTL "
            "— run 'super-skill prune --apply' to reclaim"
        )
    else:
        line += f"all within the {ttl}-day TTL"
    typer.echo(line, err=True)


@app.command()
def prune(
    days: int | None = typer.Option(
        None, "--days",
        help=f"Keep events within N days (default {DEFAULT_EVENT_TTL_DAYS}, env "
        "SUPER_SKILL_EVENT_TTL); older event days are pruned (FR-CAP-6).",
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Actually delete. Default is a dry-run that only reports.",
    ),
) -> None:
    """Prune captured event days older than the TTL (default 14 days; dry-run)."""
    ttl = days if days is not None else _event_ttl_days()
    log = EventLog()
    pruned = log.prune(days=ttl, apply=apply)
    if not pruned:
        typer.echo(f"nothing to prune (all event days within {ttl} days)")
        return
    verb = "pruned" if apply else "would prune (dry-run — pass --apply to delete)"
    typer.echo(f"{verb} {len(pruned)} day(s): {', '.join(pruned)}")


@app.command()
def status() -> None:
    """Registry summary: location, git head, skill/version/candidate counts."""
    reg = _registry()
    records = reg.list_skills()
    active = sum(1 for r in records if r.skill.active_version)
    versions = sum(len(r.versions) for r in records)
    cands = CandidateStore(reg.root).list()
    by_status: dict[str, int] = {}
    for c in cands:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    breakdown = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) or "none"
    typer.echo(f"state root : {reg.root}")
    typer.echo(f"git head   : {reg.head()}")
    typer.echo(f"skills     : {len(records)} ({active} active)")
    typer.echo(f"versions   : {versions}")
    log = EventLog(reg.root)
    typer.echo(f"events     : {log.count()}")
    typer.echo(f"candidates : {len(cands)} ({breakdown})")
    unmined = minestate.unmined(reg.root, log.session_ids())
    if unmined >= minestate.reminder_threshold():
        typer.echo(f"reminder   : {unmined} distinct sessions unmined "
                   f"— run `super-skill mine`")


@app.command("list")
def list_() -> None:
    """List registered skills plus any pending candidates awaiting approval."""
    reg = _registry()
    records = reg.list_skills()
    if not records:
        typer.echo("no skills registered — run `super-skill seed`")
    for r in records:
        av = r.active
        ver = r.skill.active_version or "-"
        desc = _short(av.frontmatter.description) if av else ""
        typer.echo(f"{r.skill.skill_id:<32} {ver:<5} {desc}")

    pending = [c for c in CandidateStore(reg.root).list() if c.status == "pending"]
    if pending:
        typer.echo(f"\npending candidates ({len(pending)}) — review with `candidate show <id>`:")
        for c in pending:
            typer.echo(f"  {c.candidate_id:<30} {c.session_count} sessions  {c.family_label}")


@app.command()
def show(skill_id: str) -> None:
    """Show a skill's frontmatter, version history and provenance."""
    _require_valid_name(skill_id)
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
    _require_valid_name(skill_id)
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
    if active and active not in versions:
        typer.echo(
            f"\n! active pointer {active!r} is dangling — run `super-skill doctor`",
            err=True,
        )
    elif active and rec.versions[active].parent_versions:
        prev = rec.versions[active].parent_versions[0]  # DAG parent, not insertion-pred (L20)
        typer.echo(f"\nrollback : super-skill rollback {skill_id} --to {prev}")


@app.command()
def rollback(
    skill_id: str,
    to: str = typer.Option("", "--to", help="target version; default = previous"),
    reason: str = typer.Option("", "--reason"),
    host: str = typer.Option("claude", "--host", help="re-materialize to: claude | codex | all"),
) -> None:
    """Switch the active pointer to an older version and re-materialize to the host(s)."""
    _require_valid_name(skill_id)
    reg = _registry()
    try:
        hosts = config.resolve_hosts(host)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    rec = reg.get(skill_id)
    if rec is None:
        typer.echo(f"unknown skill: {skill_id}", err=True)
        raise typer.Exit(1)
    versions = list(rec.versions)
    if not to:
        active = rec.skill.active_version
        if active and active not in versions:
            typer.echo(
                f"active pointer {active!r} is dangling — run `super-skill doctor`", err=True
            )
            raise typer.Exit(1)
        # Default target = the DAG parent of the active version, not the version
        # dict's insertion-order predecessor (they diverge after a rollback+branch, L20).
        parents = rec.versions[active].parent_versions if active else []
        if not parents:
            typer.echo("no previous version to roll back to", err=True)
            raise typer.Exit(1)
        to = parents[0]
    try:
        rec = reg.set_active(skill_id, to, op=OperationType.ROLLBACK, reason=reason or None)
        # Re-materialize to every host this skill was pushed to, not just the
        # requested --host, so a default `rollback` still fixes codex (P2-5).
        sync_hosts = sorted({*hosts, *rec.skill.materialized_hosts})
        dests = [reg.materialize(skill_id, config.host_skills_dir(h), host_name=h)
                 for h in sync_hosts]
    except RegistryError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"rolled back {skill_id} -> {to}; materialized {', '.join(str(d) for d in dests)}")


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="restore tampered/missing versions from git "
                             "and re-materialize host drift, then re-verify"),
) -> None:
    """Check registry integrity: hashes, pointers, host sync.

    Read-only by default; exits 1 if any integrity error is found. With --fix it
    restores git-recoverable versions and re-materializes host drift, then
    re-verifies — exit status reflects what remains, not what was attempted.
    Dangling pointers / name mismatches need judgment and are left to you."""
    reg = _registry()
    host = config.host_skills_dir()

    if fix:
        actions, remaining = repair(reg, host)
        for a in actions:
            mark = "✓" if a.ok else "✗"
            typer.echo(f"  {mark} {a.issue.skill_id}: {a.action}")
        if not actions:
            typer.echo("doctor --fix: nothing mechanically fixable")
        errors = [i for i in remaining if i.severity == "error"]
        for i in remaining:
            m = "✗" if i.severity == "error" else "!"
            typer.echo(f"  {m} [{i.severity}] {i.skill_id}: {i.message} (needs manual fix)")
        typer.echo(
            f"doctor --fix: {len(actions)} action(s); "
            f"{len(errors)} error(s) remain, {len(remaining) - len(errors)} warning(s)"
        )
        if errors:
            raise typer.Exit(1)
        return

    issues = check_registry(reg, host)
    if not issues:
        typer.echo("doctor: OK — registry consistent, host in sync")
        return
    errors = [i for i in issues if i.severity == "error"]
    for i in issues:
        mark = "✗" if i.severity == "error" else "!"
        typer.echo(f"  {mark} [{i.severity}] {i.skill_id}: {i.message}")
    typer.echo(f"doctor: {len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    if errors:
        raise typer.Exit(1)


@app.command("status-reminder")
def status_reminder() -> None:
    """SessionStart hook helper: print the unmined-backlog reminder envelope
    (JSON) when the backlog crosses the nudge threshold; print nothing
    otherwise. Never fails the session (NFR-3): any internal error is
    swallowed and the command exits 0 silently."""
    try:
        payload = hooks.status_reminder_json(config.state_root())
    except Exception:  # noqa: BLE001 — hook helper must never break a session
        return
    if payload:
        typer.echo(payload)


@app.command("hooks-config")
def hooks_config(
    command: str = typer.Option("super-skill capture", "--command", help="capture invocation"),
) -> None:
    """Print the settings.json hooks block that feeds real sessions to capture.

    Prints only — merge it into ~/.claude/settings.json yourself (editing
    user-global config is your call, not the tool's)."""
    typer.echo(json.dumps(hooks_settings(command), indent=2))
    typer.echo(
        "\n# merge the above into ~/.claude/settings.json (or a project .claude/settings.json)",
        err=True,
    )


@candidate_app.command("draft")
def candidate_draft(min_sessions: int = typer.Option(3, "--min-sessions")) -> None:
    """Draft skill candidates from mined families (idempotent, pre-promotion)."""
    log = EventLog()
    families = mine_families(log.iter_events(), min_sessions=min_sessions)
    store = CandidateStore(config.state_root())
    created = draft_from_families(store, families)
    # Drafting acts on the mining, so it too clears the status reminder.
    minestate.record_mined(log.root, log.session_ids())
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
    _require_valid_name(candidate_id, "candidate id")
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
    raw = store.skill_md(candidate_id)
    findings = scan_skill_md(raw)
    if findings:
        typer.echo(f"gate       : {len(findings)} finding(s) — approve will be BLOCKED:")
        for f in findings:
            typer.echo(f"  ! {f.category} in {f.location}: {f.snippet}")
    else:
        typer.echo("gate       : clean (no injection patterns)")
    report = eval_lite(raw)
    ev = "pass" if report.passed else "FAIL"
    typer.echo(f"eval-lite  : {ev} ({'; '.join(f'{c.name}={c.detail}' for c in report.checks)})")
    if report.insufficient_evidence:
        typer.echo("           : two-arm (No Skill/Skill) = Insufficient Evidence — human accept")
    typer.echo("--- SKILL.md ---")
    typer.echo(raw)


@candidate_app.command("approve")
def candidate_approve(
    candidate_id: str,
    reason: str = typer.Option("", "--reason"),
    host: str = typer.Option("claude", "--host", help="materialize to: claude | codex | all"),
) -> None:
    """Approve a candidate: promote to the registry and materialize to the host(s)."""
    _require_valid_name(candidate_id, "candidate id")
    store = CandidateStore(config.state_root())
    reg = _registry()
    try:
        hosts = config.resolve_hosts(host)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    try:
        sv = approve(store, reg, candidate_id, config.host_skills_dir(hosts[0]),
                     host_name=hosts[0], reason=reason or None)
    except InstructionGateError as e:
        typer.echo(str(e), err=True)
        for f in e.findings:
            typer.echo(f"  ! {f.category} in {f.location}: {f.snippet}", err=True)
        typer.echo("edit the candidate's SKILL.md to remove the flagged text, then re-approve.",
                   err=True)
        raise typer.Exit(1) from e
    except EvalError as e:
        typer.echo(str(e), err=True)
        for c in e.report.failures():
            typer.echo(f"  ! {c.name}: {c.detail}", err=True)
        raise typer.Exit(1) from e
    except (CandidateError, RegistryError, SkillMdError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    # The candidate is now approved + promoted + materialized to hosts[0]. An
    # extra-host materialize failure must NOT read as an approve failure (re-running
    # approve would say "already approved") — point at the recovery command (L17).
    for extra in hosts[1:]:
        try:
            reg.materialize(sv.skill_id, config.host_skills_dir(extra), host_name=extra)
        except RegistryError as e:
            typer.echo(
                f"approved {candidate_id} -> {sv.skill_id}@{sv.version}, but materialize to "
                f"{extra} failed: {e}\n  recover with: "
                f"super-skill materialize {sv.skill_id} --host {extra}",
                err=True,
            )
            raise typer.Exit(1) from e
    dests = ", ".join(str(config.host_skills_dir(h) / sv.skill_id) for h in hosts)
    typer.echo(
        f"approved {candidate_id} -> {sv.skill_id}@{sv.version}; materialized to {dests}"
    )


@candidate_app.command("reject")
def candidate_reject(candidate_id: str) -> None:
    """Mark a candidate rejected (leaves it on disk for the record)."""
    _require_valid_name(candidate_id, "candidate id")
    store = CandidateStore(config.state_root())
    try:
        reject(store, candidate_id)
    except CandidateError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"rejected {candidate_id}")


if __name__ == "__main__":
    app()

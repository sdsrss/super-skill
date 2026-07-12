# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [0.7.0] - 2026-07-12

### Added
- **Mine reminder** — `status` now nudges (`reminder : N distinct sessions
  unmined — run mine`) once enough new sessions have accumulated since the last
  mine. A watermark (`mine_state.json`) records the distinct-session count at the
  last mine, so "unmined" is honest: it clears when you mine and only fires again
  as new sessions pile up. Threshold defaults to 3 (`SUPER_SKILL_MINE_REMINDER`
  overrides). `mine` also reports the distinct-session count when nothing yet
  clears the recurrence threshold, and both `mine` and `candidate draft` reset
  the watermark.

## [0.6.0] - 2026-07-12

### Added
- **Candidate visibility** — `status` now reports a candidate count with a
  per-status breakdown, and `list` appends a "pending candidates" section so
  drafts awaiting approval are visible without a separate command.

## [0.5.0] - 2026-07-12

### Added
- **`doctor --fix`** — mechanical repair. Restores tampered/missing versions from
  git HEAD (the committed, correct content) and re-materializes host drift, then
  **re-verifies**: the exit status reflects what remains after the fix, not what
  was attempted. Issues needing judgment (a dangling active pointer, a name
  mismatch) are reported for manual resolution rather than auto-changed.

## [0.4.0] - 2026-07-12

Hardens the v1 package manager.

### Added
- **`doctor`** — read-only registry integrity check. Re-hashes every stored
  version against the `artifact_hash` recorded at promotion (catching tampering,
  corruption, or a hand-edit that bypassed the registry), checks the active
  pointer resolves, and reports host drift. Exits 1 on an integrity error;
  remediation (`rollback` / `seed` / re-approve) is left to the user.

## [0.3.0] - 2026-07-12

Closes out the walking skeleton: `candidate approve` now runs two hard gates
before it writes anything, and real sessions can be wired into capture.

### Added
- **Instruction-layer adversarial gate** (docs/04 §2.4bis) — v1's only mandatory
  security gate. Rule-scans a candidate's body + description for external-action
  imperatives (`curl|bash`, network fetch, credential access, `ignore previous`
  overrides, run-undeclared-script) and blocks `approve` before any write. v1
  candidates are pure text the host Agent runs as trusted instructions, so a
  poisoned imperative is the code×instruction seam single-tool scanners miss.
- **Deterministic eval-lite hard gate** (docs/04 §1.6) — schema, zero
  credential/PII leak, and the agentskills token budget, checked before promote.
  The No Skill / Skill two-arm is labelled *Insufficient Evidence* at personal
  scale (no corpus/harness) rather than faked.
- **`hooks-config`** — prints the `settings.json` hooks block wiring the six host
  events to `super-skill capture`, so real sessions accumulate into the WAL.
  Print-only; you merge it into `~/.claude/settings.json` yourself.

## [0.2.0] - 2026-07-12

Completes the walking-skeleton loop: mined opportunity families can now become
human-approved skills, still routed through candidate → gate → promote (no
component writes the production skill set except on approve).

### Added
- **Candidate approval loop** — `candidate draft` scaffolds a skill from a mined
  family (an honest TODO-stub; coarse mining can name a recurring family, not
  author its procedure), `candidate list/show` review it, and `candidate approve`
  promotes the (human-editable) draft: registers an immutable ACTIVE version and
  materializes it to the host skills dir. Drafts live as pre-promotion scratch,
  git-ignored by the registry — only `approve` writes tracked state (One Writer
  Rule). `candidate reject` records a decision without promoting.

### Fixed
- **Mining noise** — coarse mining no longer treats the hook envelope as content:
  the event type is no longer seeded into the token stream, envelope keys
  (`hook_event_name` / `session_id` / `cwd` / …) are skipped, and `[REDACTED:kind]`
  placeholders are stripped. These had produced junk families (`userpromptsubmit-*`,
  cwd-derived slugs, redaction kind names).

## [0.1.0] - 2026-07-12

First release: the **M0+WS package-manager** scope. A GATE-1 measurement of the
author's own history showed the candidate opportunity flow does not yet clear the
threshold that would justify the self-learning loop (M2–M5), so v1 is deliberately
the package manager, not the factory.

### Added
- **Git-backed registry** — per-skill `meta.json` (Skill pointer + SkillVersion DAG
  + audit trail); git provides integrity, audit and rollback.
- **Seed import** — bring existing `~/.claude/skills` under version control,
  read-only on the host, idempotent by content hash.
- **CLI** — `seed`, `status`, `list`, `show`, `explain`, `rollback`.
- **WS capture pipeline** — append-only JSONL event WAL with regex redaction that
  runs before any write (secret values never reach disk; only kind + field location
  are recorded), plus coarse opportunity mining that surfaces task families
  recurring across ≥3 sessions. Exposed via `capture` (host hook, never fails the
  session) and `mine`.
- Strict typing (mypy) and lint (ruff) across the package; 41 tests.

### Notes
- Deferred to a research track: candidate generation/approval loop, optimization,
  external distillation, dynamic sandbox, signed Publisher, and the runtime Router
  (milestones M1–M5). Not published to any package registry.

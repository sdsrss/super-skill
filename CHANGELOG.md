# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

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

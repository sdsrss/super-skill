# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

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

---
name: super-skill
description: Use when the user wants to manage, version, audit, or roll back their Claude Code Agent Skills, or to review skill candidates mined from past sessions. super-skill is a git-backed package manager for the skills in ~/.claude/skills — it seeds existing skills under version control, explains where each came from, rolls any skill back one command, checks registry integrity (doctor), and surfaces recurring task families worth turning into a skill. Triggers include "version my skills", "roll back that skill", "why do I have this skill", "check my skill registry", "what could become a skill", "mine my sessions".
---

# super-skill

super-skill is a **personal package manager for Agent Skills**. It does not run
your skills — it manages the ones in `~/.claude/skills`: version history,
provenance, rollback, integrity checks, and opportunity mining. It is driven by
the `super-skill` CLI (install with `uv tool install super-skill-cli` or
`pipx install super-skill-cli`; the command stays `super-skill`).

Scope is deliberately the **package-manager** form. The self-learning loop
(auto-optimizing skills, external distillation) is a deferred research track and
is NOT part of this tool — do not imply it exists.

## When to use

- **Version / audit existing skills** → `super-skill seed` (import `~/.claude/skills`
  under version control, read-only on the host) → `super-skill list` / `status`.
- **"Why do I have this skill / where did it come from"** → `super-skill explain <id>`
  (provenance chain + audit + how to roll back).
- **A skill regressed, undo it** → `super-skill rollback <id> [--to vN]` (switches
  the active pointer and re-materializes to `~/.claude/skills`).
- **Registry health** → `super-skill doctor` (content-hash / pointer / host-sync
  check; read-only). `super-skill doctor --fix` restores git-recoverable versions
  and re-materializes drift, then re-verifies.
- **"What do I keep re-solving that could be a skill"** → `super-skill mine`
  (task families recurring across ≥3 captured sessions) → `super-skill candidate draft`
  → review → `super-skill candidate approve <id>` (runs two gates, then promotes).
- **Turn on session capture** (feeds `mine`) → `super-skill hooks-config` prints the
  settings.json hooks block for the user to merge (user-global config is theirs to
  edit). The plugin also ships these hooks in `hooks/hooks.json`.

## How to run it

Run the CLI via Bash and interpret the output for the user. Every write path is
explicit and reversible; `seed`/`doctor` (no `--fix`) are read-only. Prefer the
plugin's slash commands (`/super-skill:status`, `/super-skill:mine`,
`/super-skill:doctor`, `/super-skill:candidates`, `/super-skill:seed`) for the
common flows.

If `super-skill` is not on PATH, tell the user to install it:
`uv tool install super-skill-cli` (or `pipx install super-skill-cli`).

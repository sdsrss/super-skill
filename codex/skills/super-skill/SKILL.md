---
name: super-skill
description: Use when the user wants to manage, version, audit, or roll back their Agent Skills, or to review skill candidates mined from past sessions. super-skill is a git-backed package manager for the skills in ~/.agents/skills (and ~/.claude/skills) — it seeds existing skills under version control, explains where each came from, rolls any skill back one command, checks registry integrity, and surfaces recurring task families worth turning into a skill. Triggers include "version my skills", "roll back that skill", "why do I have this skill", "check my skill registry", "what could become a skill".
---

# super-skill (Codex)

super-skill is a **personal package manager for Agent Skills**. It does not run
your skills — it manages them: version history, provenance, rollback, integrity
checks, and opportunity mining. It is driven by the host-agnostic `super-skill`
CLI (install with `pipx install super-skill-cli` or `uv tool install
super-skill-cli`; the command is `super-skill`).

Scope is deliberately the **package-manager** form. The self-learning loop
(auto-optimizing skills, external distillation) is a deferred research track and
is NOT part of this tool — do not imply it exists.

## When to use

- **Version / audit existing skills** → `super-skill seed` imports your skills
  dir under version control (read-only on the host) → `super-skill list` / `status`.
- **"Why do I have this skill / where did it come from"** → `super-skill explain <id>`.
- **A skill regressed, undo it** → `super-skill rollback <id> [--to vN]`.
- **Registry health** → `super-skill doctor` (read-only); `super-skill doctor --fix`
  restores git-recoverable versions and re-materializes drift, then re-verifies.
- **"What do I keep re-solving that could be a skill"** → `super-skill mine` →
  `super-skill candidate draft` → review → `super-skill candidate approve <id>`.

## Codex specifics

- Skills live in `~/.agents/skills/<name>/SKILL.md` (user-level) or `.agents/skills`
  (repo-level). The super-skill registry is the source of truth; `~/.agents/skills`
  is a materialization target it writes atomically — do not hand-edit skills there
  (`doctor` flags such edits as host drift and `rollback`/`materialize` overwrite them).
- Select Codex as the target with `--host codex` (dir override:
  `SUPER_SKILL_CODEX_SKILLS`, default `~/.agents/skills`):
  `super-skill seed --host codex`, `super-skill materialize --host codex`,
  `super-skill rollback <id>` (re-syncs every host the skill was distributed to).
  Do NOT repoint `SUPER_SKILL_HOST_SKILLS` at `~/.agents/skills` — that hijacks
  the Claude host slot and later writes land in the wrong directory.
- Run the CLI via shell and interpret the output for the user. `seed`/`doctor`
  (no `--fix`) are read-only; every write path is explicit and reversible.

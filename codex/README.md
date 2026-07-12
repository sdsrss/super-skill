# super-skill for Codex

Codex adopted the [Agent Skills](https://agentskills.io) open standard: it reads
`SKILL.md` from `~/.agents/skills` (user-level) and `.agents/skills` (repo-level).
There is no marketplace/plugin install like Claude Code — a skill is just its
`SKILL.md` placed in the skills directory. This package is that skill plus a
one-line installer.

## Install

```bash
# 1. Install the host-agnostic CLI (the command stays `super-skill`)
pipx install super-skill-cli          # or: uv tool install super-skill-cli

# 2. Install the meta-skill into ~/.agents/skills (idempotent)
codex/install.sh
```

`install.sh` copies `skills/super-skill/SKILL.md` into
`~/.agents/skills/super-skill/`. Re-running it is safe.

## Use

super-skill manages the skills in your skills directory (version, explain,
rollback, integrity `doctor`, opportunity `mine`). The CLI has a **Codex Target
Adapter** — use `--host codex` (or `--host all`) to read from and write to Codex's
`~/.agents/skills`:

```bash
super-skill seed --host codex                 # import from ~/.agents/skills (read-only)
super-skill materialize --host codex          # distribute active skills to Codex
super-skill materialize <id> --host all       # push one skill to both hosts
```

`~/.agents/skills` is super-skill's canonical Codex source — Codex reads promoted
skills there directly (zero-copy). Override the path with `SUPER_SKILL_CODEX_SKILLS`.

## `agents/openai.yaml`

This package ships an optional `agents/openai.yaml` host extension (installed
alongside `SKILL.md`) with Codex UI + invocation-policy hints (`interface`,
`policy`). Only the open-standard `SKILL.md` is required; edit or remove the YAML
per your current Codex version's docs.

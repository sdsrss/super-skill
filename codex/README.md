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
rollback, integrity `doctor`, opportunity `mine`). Point it at the Codex dir:

```bash
SUPER_SKILL_HOST_SKILLS=~/.agents/skills super-skill seed     # import, read-only
SUPER_SKILL_HOST_SKILLS=~/.agents/skills super-skill status
```

Since `~/.agents/skills` is super-skill's canonical source, Codex reads promoted
skills there directly — zero-copy.

## Not included

- `agents/openai.yaml` (Codex host-extension metadata) is **optional** and its
  exact schema is Codex-version-specific — add one per the current Codex docs if
  you want custom UI metadata / invocation policy. This package intentionally
  ships only the open-standard `SKILL.md`, which every Codex version reads.
- Distributing super-skill's *produced* skills to Codex needs no extra step
  (they live in `~/.agents/skills` already). A dedicated Codex Target Adapter in
  the CLI (docs/01 FR-PUB-2) remains a P1 item.

# super-skill

Personal Agent-Skill package manager: a git-backed, versioned registry for your
Claude Code / Codex skills, with seed import, provenance/explain, and one-command
rollback.

Scope is deliberately the **M0+WS package-manager** form. The self-learning loop
(candidate mining → optimization → evaluation → promotion, milestones M2–M5) is a
deferred research track — a GATE-1 measurement of the author's own history showed
the candidate opportunity flow does not yet clear the ≥10-family threshold that
would justify building it. See `docs/` for the full plan (not distributed).

## Install

**As a Claude Code plugin** (slash commands + a meta-skill + auto-wired capture hooks):

```
/plugin marketplace add sdsrss/super-skill
/plugin install super-skill
```

This gives you `/super-skill:status`, `/super-skill:mine`, `/super-skill:doctor`,
`/super-skill:candidates`, `/super-skill:seed`, and a `super-skill` skill Claude
invokes when you ask to version, explain, or roll back a skill. The plugin drives
the `super-skill` CLI, so install that too:

**The CLI** (the plugin, hooks, and slash commands all call `super-skill` on your PATH):

```bash
uv tool install super-skill-cli      # or: pipx install super-skill-cli
super-skill status                   # command name stays `super-skill`
```

The distribution is named **`super-skill-cli`** on PyPI (the plain `super-skill`
name belongs to an unrelated package); the installed command is `super-skill`.
For a one-shot run without installing: `uvx --from super-skill-cli super-skill status`.

**For Codex** — Codex has no marketplace; it reads open-standard `SKILL.md` from
`~/.agents/skills`. Install the same CLI plus the meta-skill:

```bash
pipx install super-skill-cli          # or: uv tool install super-skill-cli
codex/install.sh                      # drops the meta-skill into ~/.agents/skills
```

Point the CLI at the Codex skills dir with `SUPER_SKILL_HOST_SKILLS=~/.agents/skills`.
See `codex/README.md`. (A Codex Target Adapter *inside* the CLI — FR-PUB-2 — is
still P1; distributing produced skills to Codex needs no extra step since they
already live in `~/.agents/skills`.)

## Develop

Uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # create venv, install deps
uv run pytest                 # tests
uv run pytest tests/test_seed.py::test_seed_is_idempotent   # single test
uv run ruff check .           # lint
uv run mypy super_skill/      # typecheck
```

## Use

```bash
uv run super-skill seed       # import ~/.claude/skills into the registry (read-only on host)
uv run super-skill status     # registry location, git head, counts
uv run super-skill list       # skills with active version + description
uv run super-skill show <id>  # frontmatter, versions, hashes
uv run super-skill explain <id>          # provenance chain + audit + rollback hint
uv run super-skill rollback <id> [--to vN]   # switch active pointer, re-materialize to host
uv run super-skill doctor                # registry integrity check (hashes, pointers, host sync)
uv run super-skill doctor --fix          # restore git-recoverable versions + re-materialize drift
```

`doctor` is read-only: it re-hashes every stored version against the hash
recorded at promotion (catching tampering or a hand-edit that bypassed the
registry), checks the active pointer resolves, and reports host drift. It exits 1
on an integrity error. `--fix` restores tampered/missing versions from git HEAD
and re-materializes host drift, then **re-verifies** — the exit status reflects
what remains, not what was attempted. Issues needing judgment (a dangling active
pointer, a name mismatch) are left for you (`rollback` / `seed` / re-approve).

Capture → mine → approve loop:

```bash
uv run super-skill hooks-config          # print the settings.json hooks block (merge it yourself)
uv run super-skill capture               # append one host hook event (JSON on stdin); never fails
uv run super-skill mine                  # surface task families recurring across ≥3 sessions
uv run super-skill candidate draft       # scaffold candidates from mined families (TODO-stubs)
uv run super-skill candidate show <id>   # draft + gate findings + eval-lite result
uv run super-skill candidate approve <id># promote to registry + materialize to host
```

`approve` runs two hard gates before any write: the instruction-layer adversarial
gate (rejects `curl|bash` / credential / `ignore previous` imperatives) and a
deterministic eval-lite (schema, zero secret leak, token budget). The No Skill /
Skill two-arm is labelled *Insufficient Evidence* at personal scale. To wire real
sessions in, run `hooks-config` and merge its output into `~/.claude/settings.json`.

State lives in `~/.super-skill/` (a git repo — audit and rollback are git). Override
with `SUPER_SKILL_HOME`; override the host skills dir with `SUPER_SKILL_HOST_SKILLS`.

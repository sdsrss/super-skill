# super-skill

Personal Agent-Skill package manager: a git-backed, versioned registry for your
Claude Code / Codex skills, with seed import, provenance/explain, and one-command
rollback.

Scope is deliberately the **M0+WS package-manager** form. The self-learning loop
(candidate mining → optimization → evaluation → promotion, milestones M2–M5) is a
deferred research track — a GATE-1 measurement of the author's own history showed
the candidate opportunity flow does not yet clear the ≥10-family threshold that
would justify building it. See `docs/` for the full plan (not distributed).

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
```

`doctor` is read-only: it re-hashes every stored version against the hash
recorded at promotion (catching tampering or a hand-edit that bypassed the
registry), checks the active pointer resolves, and reports host drift. It exits 1
on an integrity error; fixes are yours to run (`rollback` / `seed` / re-approve).

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

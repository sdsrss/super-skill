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
```

State lives in `~/.super-skill/` (a git repo — audit and rollback are git). Override
with `SUPER_SKILL_HOME`; override the host skills dir with `SUPER_SKILL_HOST_SKILLS`.

<!-- SEO: Claude Code Agent Skills package manager — version control, rollback, provenance, integrity checks for ~/.claude/skills and ~/.agents/skills (Codex). -->

# super-skill

**Version control, rollback, and provenance for your Claude Code and Codex Agent Skills.**
super-skill is a git-backed package manager for the skills in `~/.claude/skills`
(and Codex's `~/.agents/skills`): it puts every skill under version history,
tells you where each one came from, rolls any skill back with one command, and
checks the registry for tampering — with secret-redacted session capture and
safety-gated promotion built in.

**English** · [简体中文](README.zh-CN.md)

---

## Why super-skill

Agent Skills are just Markdown files in a directory. That directory has no
history: edit a `SKILL.md` and the previous version is gone; you can't tell which
skill came from where, why it's there, or whether one was quietly changed. There
is no undo.

super-skill treats your skills like packages: **versioned, auditable, reversible.**

## Highlights

- **One-command rollback** — a skill regressed? `super-skill rollback <id>` switches
  the active version and re-materializes it to your skills directory.
- **Provenance & audit** — `super-skill explain <id>` answers *why does this skill
  exist, where did it come from, how do I undo it* from an immutable audit trail.
- **Tamper detection** — `super-skill doctor` re-hashes every stored version against
  the hash recorded at promotion; `--fix` restores git-recoverable versions.
- **Redaction before disk** — session capture strips secrets and private paths
  *before* anything is written; secret values never reach the log.
- **Safety-gated promotion** — a candidate becomes a skill only through two hard
  gates (an instruction-layer adversarial scan + a deterministic eval-lite). The
  scan is a *rule* gate — it flags direct English/Chinese imperatives and known
  obfuscations, not arbitrary paraphrase — so it is a backstop, not a guarantee:
  always read the full SKILL.md before approving.
- **Runs where your agent runs** — a Claude Code plugin, a Codex install package,
  and a host-agnostic CLI, all driven by the same `super-skill` command.

## Install

### Claude Code (plugin)

```
/plugin marketplace add sdsrss/super-skill
/plugin install super-skill
```

Adds slash commands (`/super-skill:status`, `:mine`, `:doctor`, `:candidates`,
`:seed`), a `super-skill` skill Claude invokes when you ask to version, explain,
or roll back a skill, and capture hooks. The plugin drives the CLI, so install
that too:

### CLI

```bash
uv tool install super-skill-cli      # or: pipx install super-skill-cli
super-skill status                   # the command is `super-skill`
```

The PyPI distribution is **`super-skill-cli`** (the bare `super-skill` name
belongs to an unrelated package); the installed command is `super-skill`.
One-shot, no install: `uvx --from super-skill-cli super-skill status`.

### Codex

Codex reads open-standard `SKILL.md` from `~/.agents/skills` — no marketplace
needed:

```bash
pipx install super-skill-cli
codex/install.sh                     # drops the meta-skill into ~/.agents/skills
```

The CLI speaks Codex natively via `--host codex` — `super-skill seed --host codex`,
`super-skill materialize --host codex` (or `--host all` for both hosts). See
[`codex/README.md`](codex/README.md).

## Features

| Command | What it does |
|---|---|
| `seed` | Import existing `~/.claude/skills` under version control — read-only on the host, idempotent by content hash. |
| `status` / `list` | Registry summary (skills, versions, events, candidates) and the skill list. |
| `show <id>` | Frontmatter, version history, and content hashes for one skill. |
| `explain <id>` | Provenance chain + audit trail + the exact rollback command. |
| `rollback <id> [--to vN]` | Switch the active version and re-materialize it to the host(s). |
| `materialize [id] --host claude\|codex\|all` | Distribute active skill(s) to Claude Code and/or Codex (the Codex Target Adapter). |
| `doctor` / `doctor --fix` | Integrity check (hashes, active pointer, host sync); `--fix` restores git-recoverable versions and re-materializes drift, then re-verifies. |
| `capture` | Append a host event to the redacted WAL — reads hook JSON on stdin, never fails the session. |
| `mine` | Surface task families recurring across ≥3 distinct sessions (`status` and the SessionStart hook nudge you once enough new sessions accumulate). |
| `prune [--days N] [--apply]` | Delete captured event days older than the TTL (FR-CAP-6); dry-run by default, `--apply` to delete. |
| `candidate draft/show/approve/reject` | Turn a mined family into a skill: draft → review → three blocking checks (gate scan, placeholder check, eval-lite) → promote & materialize. |
| `hooks-config` | Print the `settings.json` hooks block that wires session capture. |

State lives in `~/.super-skill/` — a real git repository, so **audit and rollback
are git.**

## How it's different

|  | Plain `~/.claude/skills` | super-skill |
|---|:---:|:---:|
| Version history per skill | ✗ | ✓ (git-backed DAG) |
| One-command rollback | ✗ | ✓ |
| Provenance / "why is this here" | ✗ | ✓ |
| Tamper / drift detection | ✗ | ✓ (`doctor`) |
| Secret redaction on capture | ✗ | ✓ (before disk) |
| Safety-gated promotion | ✗ | ✓ (3 blocking checks) |
| Claude Code **and** Codex | manual | ✓ one CLI |

super-skill is a **package manager, not a skill generator**: it manages, versions,
and audits the skills you already have or approve — it does not write skills for
you or change their behavior behind your back. Every write path is explicit and
reversible; your skills directory is only ever written on `approve`, `rollback`,
`materialize`, or `doctor --fix` (`seed` reads it but never modifies it).

## Usage

```bash
# Bring your current skills under version control
super-skill seed
super-skill status

# See where a skill came from and how to undo it
super-skill explain my-skill

# Undo a bad change
super-skill rollback my-skill

# Check nothing was tampered with; repair recoverable drift
super-skill doctor
super-skill doctor --fix

# Turn recurring work into a skill (capture must be wired first — see hooks-config)
super-skill mine
super-skill candidate draft
super-skill candidate show <id>      # edit the draft, then:
super-skill candidate approve <id>
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `SUPER_SKILL_HOME` | `~/.super-skill` | Registry + control state (a git repo). |
| `SUPER_SKILL_HOST_SKILLS` | `~/.claude/skills` | Claude Code skills directory (`--host claude`). |
| `SUPER_SKILL_CODEX_SKILLS` | `~/.agents/skills` | Codex skills directory (`--host codex`). |
| `SUPER_SKILL_MINE_REMINDER` | `20` | Distinct unmined sessions before `status`/SessionStart nudge you to mine; `0` disables the reminder. |
| `SUPER_SKILL_EVENT_TTL` | `14` | Days of raw captured events kept; `prune` deletes older event days (dry-run by default). |

## Scope

super-skill is deliberately the **package-manager** form (milestones M0 + WS). The
self-learning loop — automatically optimizing, distilling, and promoting skills
(milestones M1–M5) — is a **deferred research track**: a measurement of real usage
did not clear the threshold that would justify building it, so v1 is frozen as a
package manager with audit and rollback. It does not self-evolve your skills, and
this README does not imply it does.

## FAQ

**Does super-skill run or change my skills' behavior?**
No. It manages the files (version, audit, rollback, integrity) and never edits a
skill's content on its own. Approving a candidate promotes a draft *you* reviewed.

**Will it touch `~/.claude/skills` without asking?**
Four commands write there — `approve` (promote a reviewed candidate), `rollback`,
`materialize`, and `doctor --fix`. `seed` reads your skills into the registry but
never modifies them; `status`/`list`/`show`/`explain`/`doctor` are read-only.

**Are my secrets safe in captured sessions?**
Redaction runs *before* any write: secret values and private paths never reach the
log. Capture is off until you wire it (`super-skill hooks-config`).

**Do I need PyPI for the plugin to work?**
The plugin calls the `super-skill` CLI on your PATH. Install it from PyPI:
`uv tool install super-skill-cli` (or `pipx install super-skill-cli`).

**Does it support Codex?**
Yes — the same CLI plus a `codex/` install package for `~/.agents/skills`. The CLI
has a Codex Target Adapter: `--host codex` on `seed`, and `--host codex|all` on
`approve`, `rollback`, and `materialize` (a plain `rollback` also re-syncs every
host the skill was distributed to), reading from and writing to Codex's
`~/.agents/skills`.
The Codex package also ships an optional `agents/openai.yaml` host extension.

## Develop

Uses [uv](https://docs.astral.sh/uv/). Python 3.12.

```bash
uv sync                       # venv + deps
uv run pytest                 # tests
uv run ruff check .           # lint
uv run mypy super_skill/      # typecheck
```

## License

[MIT](LICENSE) © sdsrss

# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

### Changed
- Mine-backlog reminder default threshold raised 3 → 20 unmined sessions, and
  `SUPER_SKILL_MINE_REMINDER=0` now means "reminder off" (previously it fired
  forever and `mine` could never clear it); invalid/negative values warn and
  fall back instead of silently defaulting. At threshold 3 a heavy
  multi-session user was nudged at nearly every session opening.
- `mine` and `candidate draft` now cap output at the top 20 families by
  recurrence (`--top N` / `--all` to change); `mine` previously printed every
  family (73k+ lines on real data) and one `draft` run could create thousands
  of candidate directories. The hidden/undrafted remainder is reported on
  stderr.
- A stricter-than-default `--min-sessions` no longer counts as reviewing the
  backlog: `mine --min-sessions 999` used to print "no families" yet cleared
  the entire reminder watermark. `candidate draft` likewise records the
  watermark only when it actually drafted something.
- Families whose label slugifies to nothing (pure-Chinese/punctuation) draft
  under a stable `family-<hash>` id instead of being silently skipped with a
  false "nothing mined" message, and two labels that collapse onto the same
  slug get disambiguated with a hash suffix instead of the later one being
  swallowed — mined Chinese sessions can now actually become candidates.

### Added
- `mine` now ends with an `events on disk:` footer (stderr) reporting the raw-event
  WAL footprint and, when event days have aged past the FR-CAP-6 TTL, a one-line
  `super-skill prune --apply` reclaim hint — so the WAL's growth is visible at the
  moment the user is already looking at captured data. The `/super-skill:mine`
  plugin command offers to run the prune on the user's behalf when the footer
  flags prunable days. Deletion itself remains explicit and human-confirmed;
  nothing is auto-pruned.

### Fixed
- TTL hardening (review round on the footer change): an unparseable
  `SUPER_SKILL_EVENT_TTL` now warns and falls back to the 14-day default on both
  the footer and `prune` (previously `prune` exited 2, so the footer could
  recommend a command that then failed); a negative TTL clamps to 0 instead of
  computing a future cutoff that would have deleted today's events; a TTL large
  enough to overflow the date range means "nothing is stale" instead of crashing;
  and the footer's day count now uses `prune`'s definition of a day (date-named
  dirs only), so it never reports days that can't be reclaimed.

## [0.13.0] - 2026-07-13

A hardening release implementing the full v0.12.1 comprehensive-audit roadmap
(18 items across strategy calibration, privacy, load-bearing guardrails,
resilience, and consistency) plus a code-review round. All test-driven:
186 → 223 passing tests; `ruff` and `mypy --strict` clean. Backward-compatible.

### Added
- `super-skill prune [--days N] [--apply]` — deletes captured event days past the
  FR-CAP-6 TTL (default 14 days, `SUPER_SKILL_EVENT_TTL`; dry-run by default,
  `--apply` to delete). Delivers the retention bound that was previously only a
  docstring claim, so a long-running capture WAL no longer grows unbounded.
- Multi-host consistency tracking. A skill now records which hosts it was
  distributed to (`materialized_hosts`); `rollback` re-materializes to *every*
  tracked host — so a default `rollback` also re-syncs Codex, not just Claude —
  and `doctor`/`doctor --fix` verify and repair per-host drift instead of only
  looking at the Claude directory.
- Forward-compatible on-disk state. A `schema_version` stamp is written into
  `meta.json`, `candidate.json`, and each WAL line; persisted models read with
  `extra="ignore"` so an older CLI tolerates (drops) fields a newer super-skill
  added rather than failing with "corrupt". Truncated/type-invalid state still
  surfaces as a clean error.

### Fixed
- Chinese blind spot in the mining/eval instruments. The opportunity miner now
  emits CJK bigrams (previously non-ASCII text was replaced with spaces, so a
  Chinese session mined to almost nothing) and the eval-lite token budget counts
  CJK characters (~1.5 chars/token) instead of estimating a 3000-character
  Chinese body as ~1 token.
- The instruction-layer approval gate now covers Chinese prompt-injection/exfil
  phrasing, `base64 -d | sh` decode-pipes, and env-collect-and-transmit patterns.
  Its docstring and the READMEs no longer imply the rule scan is a safety
  guarantee — it is a backstop, and approving still requires reading the full
  SKILL.md.
- Concurrent registry writes no longer lose updates. A re-entrant `fcntl` advisory
  lock guards the read-modify-write + git-commit critical section (also removing
  a `git add` / `index.lock` race). Atomic writes are chmod `0o600`.
- A candidate still carrying its unedited TODO / "EDIT before approving" scaffold
  is blocked at approve, so a hollow skill can't be promoted and start routing.
- A dangling active-version pointer no longer crashes `explain` / `rollback`
  (they now point you at `doctor`), and `rollback`'s default target is the DAG
  parent rather than the version dict's insertion-order predecessor.
- Redaction adds JWT and URL basic-auth (`user:pass@host`) patterns and a 256 KB
  per-leaf payload cap (redact first, then truncate).
- A failed `git commit` surfaces as `RegistryError` (caught by the CLI) instead
  of a raw `CalledProcessError` traceback.

### Security
- User-supplied skill and candidate ids are validated against `NAME_RE` before
  reaching a filesystem path (no `../` traversal), and an unknown `--host` now
  raises instead of silently defaulting to the Claude skills directory.

## [0.12.1] - 2026-07-13

Mine-backlog reminder UX fix. Backward-compatible.

### Fixed
- The SessionStart mine-backlog reminder now points at a path the user can
  actually act on. Previously it advertised only the bare `super-skill mine`
  CLI string, which is a dead end inside a Claude Code chat (no terminal, no
  PATH) — users tried to run it as a slash command and found nothing. The
  reminder now: (1) is explicitly labelled as coming from the super-skill
  plugin, (2) makes "reply yes → the assistant runs mining for you" the primary
  one-tap accept path (works regardless of install shape), and (3) surfaces the
  `/super-skill:mine` slash command for plugin installs, with the raw CLI kept
  only as a terminal fallback.

### Added
- Plugin-native `hooks/hooks.json` now wires the `status-reminder`
  SessionStart/`startup` helper. Previously only the `hooks-config` settings.json
  output carried it, so users who installed via the marketplace plugin (rather
  than merging `hooks-config`) never received the mine-backlog nudge.

## [0.12.0] - 2026-07-13

Proactive mine-backlog reminder. Backward-compatible (additive command +
additive hooks-config entry).

### Added
- **`super-skill status-reminder`** — SessionStart hook helper. When the
  unmined-sessions backlog crosses the nudge threshold it prints a JSON
  `hookSpecificOutput` envelope whose injected context makes the session's
  assistant proactively tell the user about the backlog, show the
  `super-skill mine` command, and offer a yes/no to run it on their behalf;
  otherwise it prints nothing. Exit code is always 0 and internal errors are
  swallowed — a hook helper must never fail the host session (NFR-3).
- **`hooks-config` wires the reminder automatically**: the generated
  SessionStart block gains a second entry (matcher `"startup"`) invoking the
  sibling `status-reminder` command, derived from the same command prefix as
  `capture` (custom prefixes follow along).

Tests 181 → 186; `ruff check` / `mypy --strict` clean.

## [0.11.2] - 2026-07-12

Mining signal-to-noise fix. Backward-compatible.

### Fixed
- **`mine` no longer surfaces harness notification boilerplate as task families.**
  Task-notification envelopes ride inside payload VALUES (e.g. a Stop event's
  `last_assistant_message`), invisible to the existing envelope-KEY skip:
  template prose ("fires each time … may notify more than once"), tool-use ids,
  output-file paths and usage metrics mined into ~24 junk families of the top 50
  on real data. Metadata elements (`summary`/`note`/`task-id`/`tool-use-id`/
  `output-file`/`usage`) are now stripped wholesale (bounded quantifiers, no
  backtracking risk); other markup loses only its tags, so `<result>` content
  still mines. Live re-mine after the fix: 0 harness-noise families.
- **`super-skill mine | head` no longer silently loses the watermark.** The
  mined-sessions watermark was recorded after the family listing printed, so
  SIGPIPE from a closed downstream pipe killed the process first and every
  session stayed "unmined" (`status` kept nagging). The watermark is now
  recorded before printing.

### Added (repo-only, not shipped in the wheel)
- `evals/release-family/`: B′ pilot harness — 5 sealed release-family cases +
  2 negative controls with deterministic tier-1 verifiers, directory-shaped
  grader, 4-criteria verdict tooling (`report.py`), and the raw results of the
  51-run blind experiment (design docs/10, report docs/11; verdict: FAIL on
  the investment criterion — pilot closed as designed).

Tests 164 → 181; `ruff check` / `mypy --strict` clean.

## [0.11.1] - 2026-07-12

Follow-up patch from a code review of 0.11.0. Fixes a **Critical ReDoS regression
the 0.11.0 redaction hardening introduced** plus four gaps. Backward-compatible;
upgrade recommended over 0.11.0 (`pip install -U super-skill-cli`).

### Security
- **Fix ReDoS in the redaction `assigned_secret` rule** (regression in 0.11.0) —
  the broadened rule used unbounded `[A-Za-z0-9_]*` runs, so underscore-heavy
  input (snake_case blobs, env dumps) backtracked catastrophically: a ~6 KB
  payload took ~21 s. Since redaction runs on every captured event, a normal
  hook payload could hang `super-skill capture` (worse than the crash 0.11.0 was
  hardening). Runs are now bounded (`{0,64}`); the same payload processes in
  ~18 ms and secrets still redact.
- **`sk-proj-`/`sk-svcacct-` OpenAI keys are now fully redacted** — the body may
  contain `_`/`-`, and the previous rule stopped at the first such char, leaking
  the tail.
- **A secret in a keyword-named frontmatter field is now caught** — the gate and
  eval-lite serialized frontmatter with JSON, which quoted the key (`"token":`)
  and broke the `keyword: value` secret pattern; they now use YAML, preserving
  adjacency.
- **The gate folds uppercase homoglyphs** — the confusables map was lowercase
  only, so `СURL … | bash` (uppercase Cyrillic) slipped through; normalization
  now casefolds first.

### Fixed
- **`capture` survives deeply-nested JSON** — `json.loads` raises `RecursionError`
  (a `RuntimeError`, not `JSONDecodeError`) on very deep input; the parse guard
  now exits 0 on any error (NFR-3).
- The WAL append loops on short writes so a very large line can't be truncated.

## [0.11.0] - 2026-07-12

Security & reliability hardening from a full production-readiness audit. All fixes
are backward-compatible; defaults unchanged. **Recommended upgrade** if you wire
live capture via `hooks-config` — the capture/redaction path had secret-leak and
crash-safety gaps that this release closes.

**Migration**: none required. An existing `mine_state.json` from 0.10.0 is auto-
handled (the watermark format changed to a session-id set; an old file reads as
"nothing mined" and self-heals on the next `mine`). **Revert path**: pin the prior
release with `pip install super-skill-cli==0.10.0`.

### Security
- **Redaction no longer leaks underscore-delimited env-var secrets** — `DB_PASSWORD=…`,
  `AWS_SECRET_ACCESS_KEY=…`, `SECRET_KEY=…` etc. were written verbatim to the WAL
  because the keyword rule anchored on `\b` (an underscore is a word char). The
  same `redact_text` feeds the eval-lite secret gate, so this closed a leak in
  both paths at once.
- **Redaction now matches current key formats** — OpenAI `sk-proj-`/`sk-svcacct-`,
  Stripe `sk_live_`/`sk_test_`, GitHub fine-grained PATs `github_pat_`, and GCP
  `AIza…` keys were previously unmatched.
- **The instruction-layer gate + eval-lite scan the full frontmatter**, not just
  `description` + body — an injection or secret in any other frontmatter field
  (e.g. `instructions:`, `metadata:`) previously shipped to the host unscanned.
- **The gate normalizes cheap obfuscation** (NFKC + zero-width strip + common
  Cyrillic/Greek homoglyph fold) so `с​url … | bash` and homoglyph variants no
  longer slip a shell pipe past the ASCII rules.
- **The capture WAL and mine watermark are gitignored** — `events/` and
  `mine_state.json` are no longer swept into the registry's audit history by
  `git add -A`, keeping (redacted-but-private) session content out of the repo.
- **Redaction depth is capped** so a pathologically nested payload can't
  `RecursionError`; the over-deep subtree is dropped rather than leaked.

### Fixed
- **`capture` never fails the host session (NFR-3)** — non-object JSON on stdin
  and any WAL write error are now swallowed with exit 0; previously a list/scalar
  payload raised and exited 1.
- **The WAL tolerates a torn/partial line** — a hook killed mid-append no longer
  bricks every reader (`status`/`mine`/`count`); the bad line is skipped.
- **Concurrent captures no longer corrupt the WAL** — each event is one atomic
  `O_APPEND` write instead of a buffered write that could interleave across
  processes.
- **Registry/candidate/watermark writes are atomic** (temp + `os.replace`), and a
  corrupt `meta.json`/`candidate.json` surfaces as a typed error instead of a raw
  traceback that crashed `status`/`list`/`doctor`.
- **`approve` is crash-idempotent** — a crash between the registry commit and
  marking the candidate approved no longer double-promotes on re-run.
- **`seed` skips a skill whose frontmatter `name` ≠ its directory name**, so two
  host dirs sharing a name can no longer collapse into one version chain.
- **The `mine` reminder survives WAL TTL pruning** — the watermark tracks mined
  session ids, so new sessions still count as "unmined" after old ones roll off.
- **`init` rebuilds a missing/stale `.gitignore`** even when `.git` already exists.

### Changed
- Docs `02`/`03`/`04` bumped to v1.4 with WS-vs-target implementation notes
  (registry-as-source distribution, WS entity/eval-lite subsets) for doc↔code
  consistency. Test suite grew 127 → 159; `gate.py` and `redact.py` at 100%
  line coverage.

## [0.10.0] - 2026-07-12

### Added
- **Codex Target Adapter** (docs/01 FR-PUB-2) — the CLI now distributes to more
  than one host. `seed`, `approve`, `rollback`, and a new `materialize` command
  take `--host claude | codex | all`; `codex` reads/writes `~/.agents/skills`
  (override with `SUPER_SKILL_CODEX_SKILLS`), `all` targets both hosts. Defaults
  stay `claude`, so existing behavior is unchanged.
- **`materialize [skill_id] --host …`** — explicitly (re)distribute one skill, or
  all active skills, to Claude Code and/or Codex.
- **`codex/agents/openai.yaml`** — an optional Codex host-extension shipped with
  the meta-skill (`interface` display name + `policy.allow_implicit_invocation`),
  installed alongside `SKILL.md` by `codex/install.sh`. Schema per the Codex
  build-skills docs; kept to the fields super-skill needs.

### Notes
- Self-learning (M1–M5) remains gated off by the H1 falsification GATE — not
  built. The Codex adapter here is packaging/distribution (FR-PUB-2), not the
  self-learning track.

## [0.9.2] - 2026-07-12

### Changed
- **README rewritten and aligned to shipped features** — bilingual (English
  default + `README.zh-CN.md`), with install (Claude Code plugin / CLI / Codex),
  a feature table, a differentiation comparison, usage, configuration, an honest
  scope note, and an FAQ. Corrected the write-path description: the host skills
  directory is written by `approve` / `rollback` / `doctor --fix` (`seed` is
  read-only on the host). Added a GitHub repo description and topics.

## [0.9.1] - 2026-07-12

### Fixed
- **`codex/install.sh` now ships executable** — it was committed with mode 100644,
  so a fresh clone could only run it as `bash codex/install.sh`, not `./codex/install.sh`
  as the README shows. Set the git exec bit (100755). The guard test now checks the
  git-tracked mode (`git ls-files --stage`) instead of the working-tree mode, which
  some filesystems report as executable regardless.

## [0.9.0] - 2026-07-12

### Added
- **Codex install package** (`codex/`) — Codex has no marketplace; it reads
  open-standard `SKILL.md` from `~/.agents/skills`. Ships a portable `super-skill`
  meta-skill (name+description only, no Claude-specific slash commands) plus an
  idempotent `codex/install.sh` that drops it into `~/.agents/skills/super-skill/`,
  and `codex/README.md`. The CLI is host-agnostic — Codex users `pipx install
  super-skill-cli` the same way and point it at the Codex dir with
  `SUPER_SKILL_HOST_SKILLS=~/.agents/skills`.

### Notes
- No `agents/openai.yaml` is shipped — that Codex host-extension's exact schema is
  Codex-version-specific; the package ships only the open-standard SKILL.md every
  Codex version reads. A Codex Target Adapter inside the CLI (docs/01 FR-PUB-2)
  remains P1. PyPI publish is still a separate credentialed step.

## [0.8.0] - 2026-07-12

### Added
- **Claude Code plugin** — install via `/plugin marketplace add sdsrss/super-skill`
  then `/plugin install super-skill`. Ships slash commands (`/super-skill:status`,
  `:mine`, `:doctor`, `:candidates`, `:seed`), a `super-skill` meta-skill Claude
  invokes when you ask to version/explain/roll back a skill, and `hooks/hooks.json`
  wiring the six host events to `super-skill capture`. If your Claude Code build
  doesn't auto-load plugin hooks, `super-skill hooks-config` remains the reliable
  manual path.
- **PyPI-installable CLI** — packaging metadata (MIT license, classifiers, URLs)
  so the CLI installs with `uv tool install super-skill-cli` / `pipx install
  super-skill-cli`. The command stays `super-skill`.

### Changed
- **Distribution renamed to `super-skill-cli`** on PyPI — the bare `super-skill`
  name is held by an unrelated package. No action needed for anyone: prior
  releases were git tags only, never published to a package registry. The
  installed command name is unchanged (`super-skill`).

### Notes
- Codex plugin packaging stays a deferred P1 (per docs/01 FR-PUB-2). PyPI publish
  is a separate credentialed step, not performed by this release.

## [0.7.0] - 2026-07-12

### Added
- **Mine reminder** — `status` now nudges (`reminder : N distinct sessions
  unmined — run mine`) once enough new sessions have accumulated since the last
  mine. A watermark (`mine_state.json`) records the distinct-session count at the
  last mine, so "unmined" is honest: it clears when you mine and only fires again
  as new sessions pile up. Threshold defaults to 3 (`SUPER_SKILL_MINE_REMINDER`
  overrides). `mine` also reports the distinct-session count when nothing yet
  clears the recurrence threshold, and both `mine` and `candidate draft` reset
  the watermark.

## [0.6.0] - 2026-07-12

### Added
- **Candidate visibility** — `status` now reports a candidate count with a
  per-status breakdown, and `list` appends a "pending candidates" section so
  drafts awaiting approval are visible without a separate command.

## [0.5.0] - 2026-07-12

### Added
- **`doctor --fix`** — mechanical repair. Restores tampered/missing versions from
  git HEAD (the committed, correct content) and re-materializes host drift, then
  **re-verifies**: the exit status reflects what remains after the fix, not what
  was attempted. Issues needing judgment (a dangling active pointer, a name
  mismatch) are reported for manual resolution rather than auto-changed.

## [0.4.0] - 2026-07-12

Hardens the v1 package manager.

### Added
- **`doctor`** — read-only registry integrity check. Re-hashes every stored
  version against the `artifact_hash` recorded at promotion (catching tampering,
  corruption, or a hand-edit that bypassed the registry), checks the active
  pointer resolves, and reports host drift. Exits 1 on an integrity error;
  remediation (`rollback` / `seed` / re-approve) is left to the user.

## [0.3.0] - 2026-07-12

Closes out the walking skeleton: `candidate approve` now runs two hard gates
before it writes anything, and real sessions can be wired into capture.

### Added
- **Instruction-layer adversarial gate** (docs/04 §2.4bis) — v1's only mandatory
  security gate. Rule-scans a candidate's body + description for external-action
  imperatives (`curl|bash`, network fetch, credential access, `ignore previous`
  overrides, run-undeclared-script) and blocks `approve` before any write. v1
  candidates are pure text the host Agent runs as trusted instructions, so a
  poisoned imperative is the code×instruction seam single-tool scanners miss.
- **Deterministic eval-lite hard gate** (docs/04 §1.6) — schema, zero
  credential/PII leak, and the agentskills token budget, checked before promote.
  The No Skill / Skill two-arm is labelled *Insufficient Evidence* at personal
  scale (no corpus/harness) rather than faked.
- **`hooks-config`** — prints the `settings.json` hooks block wiring the six host
  events to `super-skill capture`, so real sessions accumulate into the WAL.
  Print-only; you merge it into `~/.claude/settings.json` yourself.

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

# B′ pilot log (docs/10) — raw data ledger

> Live working log. Final report goes to `docs/11-path-b-pilot-report.md`.
> Hours are wall-clock, agent-proxy caliber (both arms produced by an agent;
> the same proxy applies symmetrically — noted for criterion c).

## D4 — handwritten control arm (Arm-2)

- Producer: fresh non-fork subagent, **blind to capture data AND to the eval
  cases** (hard-isolated prompt: no file reads allowed). Prompt archived below.
- Start: 2026-07-12 15:25:47 PDT (epoch 1783895147)
- End: 2026-07-12 15:26:45 PDT (idle notification) → **wall-clock ≈ 58 s**
- Output: `handwritten/SKILL.md`, 95 lines, skill id `solo-release-publisher`.
  Covers preconditions / SemVer / version-everywhere consistency / commit→tag→
  push→release ordering / dry-run + manifest inspection / post-publish verify.
  Does NOT cover (as expected from a capture-blind arm): push-protection
  fixture handling, exit-code-remaining semantics, marketplace.json
  double-version spot, PyPI name-availability check.
- Post-editing by case-aware humans/agents: **none** (methodological rule).

### Hours snapshot for criterion (c) — early observation, verdict at D8

handwritten_total ≈ 0.016 h (58 s) vs hybrid_total ≈ 0.083 h (~5 min incl.
WAL evidence extraction + provenance tagging + gates). Hybrid is ~5× the
effort at agent speed; under the frozen rule (hybrid ≤ handwritten, or
strictly-more-passes at ≤1.5×), criterion (c) can only pass if the quality
arms diverge sharply. Absolute magnitudes are tiny (seconds vs minutes);
noted, not re-litigated — the criteria stay frozen.

### Prompt given to the control agent (verbatim, for audit)

Topic framing was domain-level only ("software release / ship workflows —
publishing a library or CLI (e.g. to npm or PyPI), tagging, pushing, creating
GitHub releases"). No case-specific hints (no mention of push-protection,
version-sync, tarball contents, exit codes, or step ordering). Format
requirements: SKILL.md frontmatter (name + trigger-precise description),
concrete checkable rules, ≤150 lines, no scripts, general knowledge only,
zero file reads.

## D5 — hybrid arm (Arm-1, the thing under test)

- Producer: main agent + captured WAL evidence; external docs only as
  edge-sharpeners.
- Evidence survey + distill + draft + gates: ~15:26 → 15:30 PDT (~5 min).
- Pipeline gates at draft (criterion b, non-destructive `candidate show`):
  instruction gate **clean**, eval-lite **pass** (frontmatter valid, no secret
  leak, ~677 tokens of 5000). `candidate approve` deferred to just before the
  hybrid runs in D6 (keeps earlier arms' host environment clean).
- Draft lives at `~/.super-skill/candidates/github-release/SKILL.md`
  (frontmatter name — authoritative skill_id — is `release-ship-workflow`).

### Provenance ledger (criterion d: mined share of load-bearing rules ≥ 50%)

Source classes: `mined` = own captured WAL event (session id cited);
`external` = official docs sharpening; `prior` = general knowledge.

| # | Rule | Provenance | Citation |
|---|------|------------|----------|
| 1 | Ship only on explicit request | mined | WAL bce8e23f (feedback #10111) |
| 2 | Verify before anything is tagged | mined | WAL 2c650213 |
| 3 | Bump every version location + grep residue | mined | WAL 905f6b5a, b2a7a7a9 |
| 4 | Exact ship order, tag pushed separately | mined | WAL 2c650213 |
| 4b | `--verify-tag` fail-fast | external | gh CLI docs |
| 5 | Secret-shaped fixtures block push; runtime assembly; soft-reset recovery | mined | WAL 6fb87dd9 |
| 6 | Inspect tarball contents pre-publish | mined | WAL 54c92879 |
| 6b | `files` whitelist / lockfile semantics | external | npm docs |
| 7 | PyPI name availability + twine check | mined | WAL 2c650213 |
| 8 | Exit by REMAINING breakage | mined | WAL 64c59c2e (doctor false-exit-0 → #8920) |

**Totals: mined 8, external 2, prior 0 → mined share 8/10 = 0.8 (≥ 0.5 ✓)**

## Methodological honesty (carries into docs/11)

1. **Case-author overlap**: the same agent designed the eval cases and
   distilled the hybrid skill, with knowledge of both. Mitigations: every
   hybrid rule cites a WAL event that predates case design; sharpening kept
   generic (no case-specific values); the handwritten arm was produced
   case-blind and capture-blind; verifiers are sealed. Residual bias risk
   stands and must be stated in the report.
2. **Hours are agent-proxy**, not human hand-writing time. Symmetric across
   arms; caliber noted for criterion (c).
3. **Capture WAL covers a single day** (global hooks wired 2026-07-12, which
   happened to be a release day). The mined rules' recurrence base is 18
   sessions in that window, not months. GATE-1's flow verdict is unaffected.
4. **WAL meta-observation worth carrying to the report**: the most valuable
   lessons are long-tail one-offs (ReDoS bound-quantifier, doctor exit-code,
   project_id bypass, npm tarball traps) — frequency clustering mathematically
   filters exactly those out. Mining-by-recurrence finds ceremonies, not
   gotchas; the hybrid arm therefore mined *content from* sessions, not
   *frequency of* sessions, for rules 5–8.

## D6 arm sequencing (planned)

no-skill runs → handwritten materialized (manual copy, logged, removed after)
→ `candidate approve` (Publisher path) → hybrid runs → negative controls
(hybrid materialized). Host mutation is announced before it happens
(user-global dir; §5).

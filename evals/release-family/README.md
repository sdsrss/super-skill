# B′ pilot harness — release/ship family

Runnable scaffold for the Path-B′ pilot (docs/10): does a **hybrid** skill —
mined primarily from the user's own captured release/ship sessions, with
external distillation only as an assist — beat both a **no-skill** baseline
and a **handwritten** control, under the four criteria frozen in
docs/10 §2 (a quality / b no-regression / c investment / d provenance)?

The target family (release/ship) was chosen by the data, not by taste: after
clearing the mine backlog it is the only coherent content family
(github release 10 sessions, manual ship 8, tag push / npm pack 6+ — see
docs/10 §1). Cases lean toward non-model-native gotchas per the #10160
probe lesson.

Everything deterministic lives here; you provide what a script cannot:
the hybrid candidate built from real capture data, the handwritten control
written in isolation, the blind agent runs, the logged hours, and the
per-rule provenance ledger.

## What's here

- `cases/case{1..5}/` — five unseen release-family tasks (positive cases):
  1. push-protection-safe secret fixture (runtime assembly);
  2. multi-manifest version sync (5 files must agree);
  3. `npm pack` tarball contents (exact file set);
  4. exit code must reflect *remaining* breakage, not attempted repairs;
  5. release step ordering (test → tag → push → release).
- `cases/n{1,2}/` — two negative controls (mechanical rename; doc
  translation). A release/ship skill must NOT trigger on these.
- Each case: `fixture/` (given to the agent), `PROMPT.md` (the task), a hidden
  `verify_test.py` (the deterministic verifier — **never show the agent**),
  and `reference/` (a known-good solution, for the fixture self-check only).
- `grader.py` — runs a case's hidden verifier against an edited fixture dir.
- `report.py` — computes the (a)(b)(c)(d) verdict from three arms + hours +
  provenance. Criteria are frozen in docs/10 §2; measuring starts only after.
- `results.template.json` — copy to `results.json` and fill in.

## Protocol (docs/10 §3, D4–D7)

1. **Handwritten control first** (D4, isolation guards against knowledge
   bleed): a fresh agent + you write a release/ship SKILL.md from scratch
   without looking at capture data. Log the authoring+debug minutes.
2. **Hybrid candidate** (D5): `super-skill candidate draft` from the mined
   release family → distill rules from your own captured events (each rule
   must cite the event/session it came from) → use external material only to
   sharpen edges/terminology → tag every load-bearing rule
   `provenance: mined|external|prior` → `candidate approve` (instruction gate
   + eval-lite run here). Log review+distill+edit minutes.
3. **Blind runs** (D6–7): per arm × case × 3 reps, a fresh non-fork subagent
   gets a copy of `fixture/` + `PROMPT.md` (never the verifier), and must
   end with a `Skills invoked:` self-report (fingerprint-cross-checked, the
   #10160 method). Negative controls: expect `Skills invoked: none`; any
   release-skill activation counts as a mistrigger.
4. **Grade**: `python grader.py cases/caseN <edited_fixture_dir>` → PASS/FAIL
   into `results.json`.
5. **Verdict**: `python report.py results.json`. All four criteria must pass;
   what each outcome means next is pre-committed in docs/10 §6.

## Fixture self-check

`tests/test_release_family_harness.py` proves the graders are trustworthy
before any arm is run: every shipped `fixture/` FAILS its hidden verifier and
every `reference/` PASSES it, and the verdict logic is unit-tested against
the frozen criteria.

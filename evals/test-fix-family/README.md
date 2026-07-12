# GATE-2 experiment harness — test/review/fix family

GATE-2 (docs/03 §3) is the second falsification measure for H1 ("evidence-gated
auto-generation has better unit-total-investment than handwriting"). It compares
a **mined** skill candidate against a **handwritten** one on the same unseen set,
and passes only if the mined one *beats* the handwritten one under three
conditions — where "beat" includes "same quality, less human effort".

This directory is the runnable scaffold. It provides everything deterministic;
you provide the three things a script cannot: a mined candidate from real usage,
the two agent runs, and your logged work-hours.

> **Precondition — this cannot be run until you have real capture data.** GATE-1
> already came in below threshold, so the go/no-go for M1+ is already decided
> (v1 = package manager). Running GATE-2 now is an optional existence-proof, not
> a release gate. There is no honest way to fabricate the mined arm.

## What's here

- `cases/case{1,2,3}/` — three unseen test-fix tasks. Each has `broken.py` (given
  to the agent), `PROMPT.md` (the task), a hidden `verify_test.py` (the
  deterministic verifier — **do not show the agent**), and `fixed.py` (reference
  solution, for the fixture self-check only).
- `handwritten/SKILL.md` — the handwritten candidate (the control arm).
- `grader.py` — runs a case's hidden verifier against a candidate solution.
- `gate2_report.py` — computes the (a)(b)(c) verdict from both arms + your hours.
- `results.template.json` — copy to `results.json` and fill in.

## Protocol

1. **Produce the mined candidate.** Install hooks (`super-skill hooks-config`),
   work normally so test/review/fix sessions accumulate, then
   `super-skill mine` → `candidate draft` → review + edit the drafted SKILL.md
   into a real skill → `candidate approve`. **Log the review+edit minutes.**
   (The handwritten arm is `handwritten/SKILL.md`; if you want a clean effort
   comparison, write your own from scratch instead and log those minutes.)
2. **Run both arms.** For each case × 3 repetitions, give the agent `broken.py`
   + `PROMPT.md` (never the verifier), once with the **mined** skill available
   and once with the **handwritten** skill available. Save each edited
   `broken.py`.
3. **Grade.** For every saved solution:
   `python grader.py cases/caseN <solution.py>` → PASS/FAIL. Record the three
   reps per case per arm into `results.json`.
4. **Verdict.** `python gate2_report.py results.json`. It reports:
   - (a) mined pass-count ≥ handwritten (ties allowed);
   - (b) no case where handwritten is 3/3 and mined is 0/3;
   - (c) tie → mined hours < handwritten hours; mined strictly more passes →
     mined hours ≤ 1.5× handwritten hours.
   PASS requires all three.

## Fixture self-check

The cases are validated in `tests/test_gate2_harness.py`: each `broken.py` fails
its verifier and each `fixed.py` passes it, so the grader is known-good before
you trust any arm's numbers.

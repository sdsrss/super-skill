---
name: systematic-test-fix
description: Fix a failing function by reproducing the failure, localizing the smallest wrong expression, making the minimal change, and re-verifying — for small bug-fix tasks with a known expected behaviour.
---

# Systematic test-fix

A discipline for fixing a function whose behaviour is wrong, when you know what
it should do. Optimises for the smallest correct change, not a rewrite.

## When to use

A single function returns wrong results for some inputs and you have concrete
expected input/output pairs (from a description or a failing check).

## Steps

1. **Restate the contract.** Write down the expected output for 2–3 inputs,
   including the boundaries and the empty/degenerate case. These are your oracle.
2. **Reproduce.** Trace the current code by hand on the input that looks most
   likely to break (a boundary, an empty input, a negative number). Confirm the
   wrong output before changing anything — do not fix by guessing.
3. **Localize.** Find the single expression responsible: an off-by-one in a
   slice or index, a `>` that should be `>=`, an accumulator initialised to `0`
   instead of the first element or negative infinity, a wrong base case.
4. **Minimal fix.** Change only that expression. Keep the signature. Resist
   refactoring unrelated code in the same edit.
5. **Re-verify against the oracle** from step 1, especially the boundary and the
   degenerate case, since those are where these bugs hide. If any still fails,
   return to step 3 — the localization was wrong, not the fix.

## Common shapes

- Slice/index endpoints (`len(x) - n` vs `len(x) - n + 1`).
- Boundary comparisons (inclusive vs exclusive).
- Accumulator seeds (`0` breaks all-negative inputs; seed with the first element
  or `float("-inf")`).
- Missing empty-input handling.

#!/usr/bin/env python3
"""GATE-2 verdict (docs/03 §3 conditions a/b/c).

Turns two arms of graded results + the human work-hours you logged into a
pass/fail verdict. "Beat" = (a) AND (b) AND (c) — quality-tie-with-less-effort
counts, per H1's unit-total-investment claim. Existence proof, not an average.

  python gate2_report.py results.json

results.json shape (see results.template.json):
  {
    "mined":       {"case1": [true,true,true], "case2": [...], ...},
    "handwritten": {"case1": [...], ...},
    "hours": {"mined_review_edit": 0.5, "handwritten_author_debug": 2.0}
  }
each list = the 3 repetitions for that case under that arm.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

Arm = dict[str, list[bool]]


def _passes(arm: Arm) -> int:
    return sum(sum(1 for r in reps if r) for reps in arm.values())


def compute_verdict(
    mined: Arm, handwritten: Arm, mined_hours: float, handwritten_hours: float
) -> dict[str, Any]:
    cases = sorted(set(mined) | set(handwritten))
    mt, ht = _passes(mined), _passes(handwritten)

    # (a) quality not worse: mined pass-count >= handwritten (ties allowed)
    a = mt >= ht

    # (b) no critical regression: no case where handwritten is 3/3 stable-pass
    #     while mined is 0/3 stable-fail
    b = not any(
        mined.get(c) is not None
        and handwritten.get(c) is not None
        and all(handwritten[c])
        and not any(mined[c])
        for c in cases
    )

    # (c) investment: tie -> mined must cost strictly less; mined-strictly-more
    #     passes -> "comparable" (<=1.5x) is enough
    if mt == ht:
        c_ok = mined_hours < handwritten_hours
        c_reason = f"tie: mined {mined_hours}h < handwritten {handwritten_hours}h ? {c_ok}"
    elif mt > ht:
        c_ok = mined_hours <= 1.5 * handwritten_hours
        c_reason = (
            f"mined more passes: mined {mined_hours}h <= 1.5x{handwritten_hours}h ? {c_ok}"
        )
    else:
        c_ok = False
        c_reason = "mined fewer passes -> (a) already fails"

    return {
        "mined_pass_total": mt,
        "handwritten_pass_total": ht,
        "a_quality_not_worse": a,
        "b_no_critical_regression": b,
        "c_investment": c_ok,
        "c_reason": c_reason,
        "verdict_pass": a and b and c_ok,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: gate2_report.py results.json", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    hours = data.get("hours", {})
    result = compute_verdict(
        data["mined"],
        data["handwritten"],
        float(hours.get("mined_review_edit", 0.0)),
        float(hours.get("handwritten_author_debug", 0.0)),
    )
    for k, v in result.items():
        print(f"{k:24} {v}")
    print("\nGATE-2:", "PASS" if result["verdict_pass"] else "FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

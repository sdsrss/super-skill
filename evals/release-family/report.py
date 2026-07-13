#!/usr/bin/env python3
"""B′ pilot verdict (docs/10 §2 criteria a/b/c/d — frozen before measurement).

Three arms (none / hybrid / handwritten) of graded results + negative-control
mistrigger count + pipeline-gate outcomes + logged hours + the provenance
ledger totals → pass/fail per criterion and overall. Existence proof, not an
average (n is single-digit by design).

  python report.py results.json

results.json shape: see results.template.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

Arm = dict[str, list[bool]]

COMPARABLE_HOURS_FACTOR = 1.5  # "工时相当" per the GATE-2 precedent (docs/10 §2 c)
PROVENANCE_MINED_MIN = 0.5  # (d): mined share of load-bearing rules (docs/10 §2 d)


def _passes(arm: Arm) -> int:
    return sum(sum(1 for r in reps if r) for reps in arm.values())


def _critical_regression(hybrid: Arm, baseline: Arm) -> bool:
    """A case where the baseline is stable-pass (all reps) while hybrid is
    stable-fail (no reps) — "不劣于" read strictly (spec §3: stricter wins)."""
    return any(
        hybrid.get(c) is not None
        and baseline.get(c) is not None
        and all(baseline[c])
        and not any(hybrid[c])
        for c in set(hybrid) | set(baseline)
    )


def compute_verdict(data: dict[str, Any]) -> dict[str, Any]:
    arms = data["arms"]
    none_arm: Arm = arms["none"]
    hybrid: Arm = arms["hybrid"]
    hand: Arm = arms["handwritten"]
    nt, yt, ht = _passes(none_arm), _passes(hybrid), _passes(hand)

    # (a) quality: hybrid >= no-skill AND not worse than handwritten, with a
    #     per-case stable-flip guard against the handwritten arm.
    a = yt >= nt and yt >= ht and not _critical_regression(hybrid, hand)

    # (b) no regression: zero mistriggers on negative controls + both mandatory
    #     pipeline gates passed + zero secret leak.
    neg = data["negative_controls"]
    gates = data["gates"]
    b = (
        int(neg["hybrid_mistriggers"]) == 0
        and bool(gates["instruction_gate_pass"])
        and bool(gates["evallite_pass"])
        and not bool(gates["secret_leak"])
    )

    # (c) investment: hybrid hours <= handwritten hours; or strictly more
    #     passes at comparable (<= 1.5x) hours.
    hours = data["hours"]
    hy, hh = float(hours["hybrid_total"]), float(hours["handwritten_total"])
    if yt > ht:
        c_ok = hy <= COMPARABLE_HOURS_FACTOR * hh
        c_reason = f"hybrid more passes: {hy}h <= {COMPARABLE_HOURS_FACTOR}x{hh}h ? {c_ok}"
    else:
        c_ok = hy <= hh
        c_reason = f"tie-or-fewer: hybrid {hy}h <= handwritten {hh}h ? {c_ok}"

    # (d) provenance: mined share of load-bearing rules >= 50% (user constraint
    #     "own-data-primary"; below that the B' claim itself is falsified).
    prov = data["provenance"]
    mined = int(prov["mined"])
    total = mined + int(prov["external"]) + int(prov["prior"])
    d_ok = total > 0 and mined / total >= PROVENANCE_MINED_MIN

    return {
        "none_pass_total": nt,
        "hybrid_pass_total": yt,
        "handwritten_pass_total": ht,
        "a_quality": a,
        "b_no_regression": b,
        "c_investment": c_ok,
        "c_reason": c_reason,
        "d_provenance": d_ok,
        "d_mined_share": round(mined / total, 3) if total else 0.0,
        "verdict_pass": a and b and c_ok and d_ok,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: report.py results.json", file=sys.stderr)
        return 2
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    result = compute_verdict(data)
    for k, v in result.items():
        print(f"{k:24} {v}")
    print("\nB' pilot:", "PASS" if result["verdict_pass"] else "FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

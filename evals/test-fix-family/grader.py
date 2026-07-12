#!/usr/bin/env python3
"""GATE-2 deterministic grader (docs/04 §1.7 tier-1: 确定性测试).

Grades one candidate solution against a case's hidden verifier. The verifier is
never shown to the agent (sealed holdout spirit, FR-EVAL-4); the grader is the
only thing that runs it. Deterministic pass/fail — no LLM in the loop.

  python grader.py <case_dir> <solution.py>      # -> prints PASS/FAIL, exits 0/1

The solution file is the agent's edited `broken.py` for that case.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def grade_case(case_dir: Path, solution: Path) -> bool:
    """True iff `solution` makes the case's hidden verifier pass."""
    case_dir, solution = Path(case_dir), Path(solution)
    with tempfile.TemporaryDirectory() as td:  # §8.V4: auto-cleaned, no residue
        tmp = Path(td)
        shutil.copy(solution, tmp / "broken.py")
        shutil.copy(case_dir / "verify_test.py", tmp / "verify_test.py")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "verify_test.py"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: grader.py <case_dir> <solution.py>", file=sys.stderr)
        return 2
    ok = grade_case(Path(argv[0]), Path(argv[1]))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

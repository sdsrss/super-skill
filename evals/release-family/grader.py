#!/usr/bin/env python3
"""B′ pilot deterministic grader (docs/10 §4, tier-1: 确定性验证).

Directory-shaped variant of evals/test-fix-family/grader.py: a case here is a
small project fixture, not a single file. The hidden verifier is never shown
to the agent (sealed holdout spirit, FR-EVAL-4); the grader is the only thing
that runs it. Deterministic pass/fail — no LLM in the loop.

  python grader.py <case_dir> <candidate_fixture_dir>   # PASS/FAIL, exit 0/1

<candidate_fixture_dir> is the agent's edited copy of the case's fixture/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def grade_case(case_dir: Path, candidate: Path) -> bool:
    """True iff `candidate` (an edited fixture dir) passes the hidden verifier."""
    case_dir, candidate = Path(case_dir), Path(candidate)
    with tempfile.TemporaryDirectory() as td:  # §8.V4: auto-cleaned, no residue
        tmp = Path(td)
        shutil.copytree(candidate, tmp / "fixture")
        shutil.copy(case_dir / "verify_test.py", tmp / "verify_test.py")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "verify_test.py"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: grader.py <case_dir> <candidate_fixture_dir>", file=sys.stderr)
        return 2
    ok = grade_case(Path(argv[0]), Path(argv[1]))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

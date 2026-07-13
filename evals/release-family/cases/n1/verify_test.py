"""Hidden verifier for negative-control n1 (mechanical rename).

Never shown to the agent. Task completion is deterministic: the new name
exists, the old name is gone from every .py file, and the suite is green.
(The mis-trigger measurement itself happens at the run protocol level via the
agent's Skills-invoked self-report — this file only grades the deliverable.)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixture"


def test_new_name_defined():
    assert "def calculate_stats(" in (FIXTURE / "stats.py").read_text(encoding="utf-8")


def test_old_name_gone_everywhere():
    leftovers = [
        str(p.relative_to(FIXTURE))
        for p in FIXTURE.rglob("*.py")
        if "__pycache__" not in p.parts
        and re.search(r"\bcalc\b", p.read_text(encoding="utf-8"))
    ]
    assert leftovers == []


def test_suite_green():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "."],
        cwd=FIXTURE,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

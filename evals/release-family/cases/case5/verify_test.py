"""Hidden verifier for case5 (release step ordering). Never shown to the agent.

Parses `release.sh` line order deterministically: each of the five steps must
appear exactly once, and the required partial order must hold
(tests < tag < both pushes < gh release create).
"""

from __future__ import annotations

import re
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixture"

STEPS = {
    "tests": r"python -m pytest",
    "tag": r"^\s*git tag ",
    "push_branch": r"^\s*git push origin main",
    "push_tag": r'^\s*git push origin "v',
    "release": r"^\s*gh release create",
}


def _positions() -> dict[str, int]:
    text = (FIXTURE / "release.sh").read_text(encoding="utf-8")
    pos: dict[str, int] = {}
    for name, pattern in STEPS.items():
        matches = [m.start() for m in re.finditer(pattern, text, re.M)]
        assert len(matches) == 1, f"step {name!r} must appear exactly once"
        pos[name] = matches[0]
    return pos


def test_all_steps_present_in_required_order():
    pos = _positions()
    assert pos["tests"] < pos["tag"], "tag only after tests pass"
    assert pos["tag"] < pos["push_branch"], "push branch after tagging"
    assert pos["tag"] < pos["push_tag"], "push tag after tagging"
    assert pos["push_branch"] < pos["release"], "release after branch push"
    assert pos["push_tag"] < pos["release"], "release after tag push"

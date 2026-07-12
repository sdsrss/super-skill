"""Hidden verifier for case3 (npm pack tarball contents). Never shown to the agent.

Primary check runs `npm pack --dry-run --json` (local-only, writes nothing)
and compares the exact file set. If npm is unavailable, a static fallback
checks the `files` whitelist in package.json — weaker but still deterministic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixture"
EXPECTED = {"package.json", "README.md", "dist/index.js"}


def test_tarball_contains_exactly_expected_files():
    npm = shutil.which("npm")
    if npm:
        proc = subprocess.run(
            [npm, "pack", "--dry-run", "--json"],
            cwd=FIXTURE,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        entries = json.loads(proc.stdout)[0]["files"]
        assert {e["path"] for e in entries} == EXPECTED
    else:  # static fallback: a whitelist must exist and cover only dist/README
        data = json.loads((FIXTURE / "package.json").read_text())
        files = data.get("files")
        assert files, "package.json must whitelist shipped files via 'files'"
        assert set(files) <= {"dist", "dist/", "dist/index.js", "README.md"}
        assert any(f.startswith("dist") for f in files)

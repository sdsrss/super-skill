"""Hidden verifier for case4 (exit code reflects remaining, not attempted).

Never shown to the agent. Runs the candidate's script against verifier-owned
manifest copies (robust even if the agent edited the shipped manifests):

1. with an unrepairable manifest present -> exit code must be non-zero,
   and the repairable ones must still have been repaired;
2. with only repairable manifests -> exit 0 and every version updated.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixture"
SCRIPT = FIXTURE / "scripts" / "sync_versions.py"
TARGET = "2.0.0"


def _valid_manifests() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted((FIXTURE / "manifests").glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def _run(manifest_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), TARGET, str(manifest_dir)],
        capture_output=True,
        text=True,
    )


def test_nonzero_exit_when_a_manifest_stays_broken(tmp_path):
    for name, text in _valid_manifests().items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "zz_unrepairable.json").write_text('{"version": ', encoding="utf-8")
    proc = _run(tmp_path)
    assert proc.returncode != 0, "exit code must reflect REMAINING breakage"
    for name in _valid_manifests():  # repair itself must still have happened
        assert json.loads((tmp_path / name).read_text())["version"] == TARGET


def test_zero_exit_when_everything_repairs_clean(tmp_path):
    valid = _valid_manifests()
    assert valid, "fixture must ship at least one repairable manifest"
    for name, text in valid.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for name in valid:
        assert json.loads((tmp_path / name).read_text())["version"] == TARGET

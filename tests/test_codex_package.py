"""Guards the Codex-side install package (docs/02 §8 adapters/codex/). Codex has
no marketplace/plugin.json — it reads the open-standard SKILL.md from
~/.agents/skills. So the package is a portable meta-skill plus an idempotent
install script that drops it into the user-level skills dir. We only assert what
the official Codex skills spec guarantees (name+description frontmatter, the
~/.agents/skills path); no fabricated manifest schema.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEX = ROOT / "codex"


def test_codex_meta_skill_open_standard_frontmatter():
    md = (CODEX / "skills/super-skill/SKILL.md").read_text(encoding="utf-8")
    assert md.startswith("---")
    assert "name: super-skill" in md
    assert re.search(r"^description:", md, re.MULTILINE)
    # portable: must not lean on Claude-only slash commands
    assert "/super-skill:" not in md


def test_install_script_exists_executable_and_targets_agents_skills():
    sh = CODEX / "install.sh"
    assert sh.exists()
    assert os.access(sh, os.X_OK), "codex/install.sh must be executable"
    body = sh.read_text(encoding="utf-8")
    assert ".agents/skills" in body
    assert "mkdir -p" in body  # idempotent create


def test_install_script_installs_into_sandbox_home():
    """Run install.sh against a throwaway HOME and assert it lands the skill."""
    sh = CODEX / "install.sh"
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "HOME": tmp}
        r = subprocess.run(["bash", str(sh)], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        installed = Path(tmp) / ".agents/skills/super-skill/SKILL.md"
        assert installed.exists()
        assert "name: super-skill" in installed.read_text(encoding="utf-8")
        # idempotent: a second run still succeeds
        r2 = subprocess.run(["bash", str(sh)], env=env, capture_output=True, text=True)
        assert r2.returncode == 0, r2.stderr

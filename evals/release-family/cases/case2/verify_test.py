"""Hidden verifier for case2 (multi-manifest version sync). Never shown to the agent.

Deterministic: every place the version lives must read 1.4.1, and no stale
version string may survive anywhere in the five files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixture"
TARGET = "1.4.1"
STALE = ("1.4.0", "1.3.9")
FILES = (
    "package.json",
    "plugin.json",
    "marketplace.json",
    "pyproject.toml",
    "src/version.py",
)


def test_package_json():
    assert json.loads((FIXTURE / "package.json").read_text())["version"] == TARGET


def test_plugin_json():
    assert json.loads((FIXTURE / "plugin.json").read_text())["version"] == TARGET


def test_marketplace_json():
    data = json.loads((FIXTURE / "marketplace.json").read_text())
    assert data["plugins"][0]["version"] == TARGET


def test_pyproject():
    text = (FIXTURE / "pyproject.toml").read_text()
    assert re.search(rf'^version = "{re.escape(TARGET)}"$', text, re.M)


def test_version_py():
    text = (FIXTURE / "src" / "version.py").read_text()
    assert re.search(rf'^__version__ = "{re.escape(TARGET)}"$', text, re.M)


def test_no_stale_version_anywhere():
    leftovers = [
        (name, stale)
        for name in FILES
        for stale in STALE
        if stale in (FIXTURE / name).read_text()
    ]
    assert leftovers == []

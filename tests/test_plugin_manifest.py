"""Guards the Claude Code plugin packaging (docs/02 §8 plugin/): manifests must
stay valid JSON, dodge the documented plugin-dev pitfalls (source "./", no
explicit path declarations), wire capture to `super-skill capture`, and keep
their versions in lockstep with the distribution version in pyproject.toml.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_plugin_json_minimal_and_valid():
    p = _json(".claude-plugin/plugin.json")
    assert p["name"] == "super-skill"
    assert p["version"] and p["description"]
    # plugin-dev pitfall: explicit path declarations trigger strict schema
    # validation that rejects common formats — Claude Code auto-scans instead.
    for forbidden in ("commands", "agents", "hooks", "mcpServers"):
        assert forbidden not in p, f"plugin.json must not declare {forbidden!r}"


def test_marketplace_source_and_shape():
    m = _json(".claude-plugin/marketplace.json")
    entry = m["plugins"][0]
    # CRITICAL pitfall: source "." causes `plugins.0.source: Invalid input`.
    assert entry["source"] == "./"
    assert entry["name"] == "super-skill"


def test_hooks_wire_all_six_events_to_capture():
    h = _json("hooks/hooks.json")
    assert h.get("description")
    hooks = h["hooks"]
    assert set(hooks) == {
        "SessionStart", "UserPromptSubmit", "Stop",
        "SessionEnd", "PreToolUse", "PostToolUse",
    }
    for entries in hooks.values():
        cmd = entries[0]["hooks"][0]["command"]
        assert "super-skill capture" in cmd


def test_manifest_versions_match_pyproject():
    v = _pyproject_version()
    assert _json(".claude-plugin/plugin.json")["version"] == v
    m = _json(".claude-plugin/marketplace.json")
    assert m["metadata"]["version"] == v
    assert m["plugins"][0]["version"] == v


def test_meta_skill_present_with_frontmatter():
    md = (ROOT / "skills/super-skill/SKILL.md").read_text(encoding="utf-8")
    assert md.startswith("---")
    assert "name: super-skill" in md
    assert "description:" in md


def test_at_least_one_slash_command():
    cmds = list((ROOT / "commands").glob("*.md"))
    assert cmds, "expected at least one commands/*.md slash command"

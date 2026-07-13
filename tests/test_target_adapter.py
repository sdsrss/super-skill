"""Codex Target Adapter (docs/01 FR-PUB-2): the CLI can resolve and distribute
active skills to more than one host — Claude Code (~/.claude/skills) and Codex
(~/.agents/skills) — via a --host selector, without disturbing the single-host
default behavior.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from super_skill import config
from super_skill.cli import app

runner = CliRunner()


def test_host_skills_dir_resolves_per_host(monkeypatch):
    monkeypatch.delenv("SUPER_SKILL_HOST_SKILLS", raising=False)
    monkeypatch.delenv("SUPER_SKILL_CODEX_SKILLS", raising=False)
    assert config.host_skills_dir().name == "skills"
    assert str(config.host_skills_dir("claude")).endswith(".claude/skills")
    assert str(config.host_skills_dir("codex")).endswith(".agents/skills")


def test_host_skills_dir_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPER_SKILL_CODEX_SKILLS", str(tmp_path / "cdx"))
    assert config.host_skills_dir("codex") == tmp_path / "cdx"


def test_host_skills_dir_rejects_unknown_host():
    """Review #3: an unknown host name must not silently resolve to the claude
    dir — a bad materialized_hosts entry would otherwise write to the wrong host."""
    with pytest.raises(ValueError, match="unknown host"):
        config.host_skills_dir("bogus")


def test_resolve_hosts():
    assert config.resolve_hosts("claude") == ["claude"]
    assert config.resolve_hosts("codex") == ["codex"]
    assert config.resolve_hosts("all") == ["claude", "codex"]
    with pytest.raises(ValueError):
        config.resolve_hosts("nope")


@pytest.fixture
def env(tmp_path, monkeypatch):
    claude = tmp_path / "claude"
    codex = tmp_path / "codex"
    claude.mkdir()
    monkeypatch.setenv("SUPER_SKILL_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SUPER_SKILL_HOST_SKILLS", str(claude))
    monkeypatch.setenv("SUPER_SKILL_CODEX_SKILLS", str(codex))
    return claude, codex


def _seed_one(claude):
    d = claude / "alpha"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: alpha\ndescription: a skill\n---\nbody\n")
    assert runner.invoke(app, ["seed"]).exit_code == 0


def test_materialize_to_codex_host(env):
    claude, codex = env
    _seed_one(claude)
    r = runner.invoke(app, ["materialize", "alpha", "--host", "codex"])
    assert r.exit_code == 0, r.output
    assert (codex / "alpha" / "SKILL.md").exists()


def test_materialize_all_hosts_all_skills(env):
    claude, codex = env
    _seed_one(claude)
    # no skill_id -> all active skills; --host all -> both dirs
    r = runner.invoke(app, ["materialize", "--host", "all"])
    assert r.exit_code == 0, r.output
    assert (claude / "alpha" / "SKILL.md").exists()
    assert (codex / "alpha" / "SKILL.md").exists()


def test_seed_reads_from_codex_host(env):
    _, codex = env
    d = codex / "beta"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: beta\ndescription: from codex\n---\nx\n")
    r = runner.invoke(app, ["seed", "--host", "codex"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["list"])
    assert "beta" in r.output


def test_bad_host_exits_1(env):
    r = runner.invoke(app, ["materialize", "--host", "bogus"])
    assert r.exit_code == 1


def test_openai_yaml_shipped_and_valid():
    from pathlib import Path

    import yaml
    p = Path(__file__).resolve().parent.parent / "codex/skills/super-skill/agents/openai.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "interface" in data
    assert data["interface"]["display_name"]
    assert data["policy"]["allow_implicit_invocation"] is True

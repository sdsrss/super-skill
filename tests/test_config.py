"""Path-resolution guardrails (audit 2026-07-13 P0-1).

An EMPTY env override used to pass through os.environ.get's default and make
Path("").expanduser() == CWD the state root — `seed` would then git-commit the
user's working tree. Empty must mean unset."""

from pathlib import Path

from super_skill import config


def test_empty_home_env_means_unset(monkeypatch):
    monkeypatch.setenv("SUPER_SKILL_HOME", "")
    assert config.state_root() == Path("~/.super-skill").expanduser()
    assert config.state_root() != Path(".")


def test_empty_host_env_means_unset(monkeypatch):
    monkeypatch.setenv("SUPER_SKILL_HOST_SKILLS", "")
    monkeypatch.setenv("SUPER_SKILL_CODEX_SKILLS", "")
    assert config.host_skills_dir("claude") == Path("~/.claude/skills").expanduser()
    assert config.host_skills_dir("codex") == Path("~/.agents/skills").expanduser()


def test_set_env_still_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPER_SKILL_HOME", str(tmp_path / "s"))
    assert config.state_root() == tmp_path / "s"

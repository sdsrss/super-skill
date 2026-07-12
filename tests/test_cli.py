import pytest
from typer.testing import CliRunner

from super_skill.cli import app

runner = CliRunner()


def _make_skill(host, name, desc, body="body"):
    d = host / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir()
    monkeypatch.setenv("SUPER_SKILL_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SUPER_SKILL_HOST_SKILLS", str(host))
    return host


def test_seed_status_list_flow(env):
    host = env
    _make_skill(host, "alpha", "first skill")
    _make_skill(host, "beta", "second skill")

    r = runner.invoke(app, ["seed"])
    assert r.exit_code == 0
    assert "2 imported" in r.output

    r = runner.invoke(app, ["status"])
    assert "skills     : 2 (2 active)" in r.output

    r = runner.invoke(app, ["list"])
    assert "alpha" in r.output and "beta" in r.output and "first skill" in r.output


def test_show_and_explain(env):
    host = env
    _make_skill(host, "alpha", "first skill")
    runner.invoke(app, ["seed"])

    r = runner.invoke(app, ["show", "alpha"])
    assert r.exit_code == 0
    assert "v1" in r.output and "DISTILLED" in r.output

    r = runner.invoke(app, ["explain", "alpha"])
    assert "seed_existing_skill" in r.output

    r = runner.invoke(app, ["show", "missing"])
    assert r.exit_code == 1


def test_rollback_reverts_host_file(env):
    host = env
    _make_skill(host, "alpha", "v1 desc", body="ORIGINAL")
    runner.invoke(app, ["seed"])
    # change host content -> seed picks up as v2
    (host / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: v2 desc\n---\nCHANGED\n"
    )
    runner.invoke(app, ["seed"])

    r = runner.invoke(app, ["rollback", "alpha", "--reason", "regressed"])
    assert r.exit_code == 0, r.output
    assert "-> v1" in r.output
    # host file must now hold the v1 body again
    assert "ORIGINAL" in (host / "alpha" / "SKILL.md").read_text()


def test_rollback_no_previous_fails(env):
    host = env
    _make_skill(host, "alpha", "only one")
    runner.invoke(app, ["seed"])
    r = runner.invoke(app, ["rollback", "alpha"])
    assert r.exit_code == 1

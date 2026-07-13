import pytest

from super_skill.doctor import DoctorIssue, check_registry, repair
from super_skill.registry import Registry
from super_skill.schemas import CandidateType


def _md(name: str, desc: str, body: str = "do the thing") -> str:
    return f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n"


@pytest.fixture
def reg(tmp_path):
    r = Registry(root=tmp_path / "state")
    r.init()
    r.add_version("alpha", _md("alpha", "first"), CandidateType.DISTILLED, [])
    return r


def test_healthy_registry_has_no_issues(reg):
    assert check_registry(reg) == []


def test_tampered_version_file_is_error(reg):
    p = reg.skills_root / "alpha" / "versions" / "v1" / "SKILL.md"
    p.write_text(_md("alpha", "first", body="TAMPERED"), encoding="utf-8")
    issues = check_registry(reg)
    assert any(i.severity == "error" and "hash" in i.message for i in issues)


def test_missing_version_file_is_error(reg):
    (reg.skills_root / "alpha" / "versions" / "v1" / "SKILL.md").unlink()
    issues = check_registry(reg)
    assert any(i.severity == "error" and "missing" in i.message for i in issues)


def test_dangling_active_pointer_is_error(reg):
    rec = reg.get("alpha")
    rec.skill.active_version = "v99"
    reg._write(rec)
    issues = check_registry(reg)
    assert any(i.severity == "error" and "active" in i.message for i in issues)


def test_frontmatter_name_mismatch_is_warn(reg):
    reg.add_version("beta", _md("not-beta", "desc"), CandidateType.CAPTURED, [])
    issues = check_registry(reg)
    assert any(i.skill_id == "beta" and i.severity == "warn" and "name" in i.message
               for i in issues)


def test_host_not_materialized_is_warn(reg, tmp_path):
    issues = check_registry(reg, host_dir=tmp_path / "host")  # never materialized
    assert any(i.severity == "warn" and "materialized" in i.message for i in issues)


def test_host_drift_is_warn(reg, tmp_path):
    host = tmp_path / "host"
    reg.materialize("alpha", host)
    (host / "alpha" / "SKILL.md").write_text(_md("alpha", "first", body="EDITED"), encoding="utf-8")
    issues = check_registry(reg, host_dir=host)
    assert any(i.severity == "warn" and "differs" in i.message for i in issues)
    # a clean materialize has no drift warning
    reg.materialize("alpha", host)
    assert not any("differs" in i.message for i in check_registry(reg, host_dir=host))


def test_issue_shape():
    i = DoctorIssue("s", "error", "boom")
    assert (i.skill_id, i.severity, i.message) == ("s", "error", "boom")


def test_multi_host_drift_detected_per_host(reg, tmp_path):
    """P2-5 / audit P2-6: a skill materialized to claude + codex, then drifted on
    codex only, must be caught on codex specifically — not reported OK because
    doctor only looked at claude."""
    claude, codex = tmp_path / "claude", tmp_path / "codex"
    reg.materialize("alpha", claude, host_name="claude")
    reg.materialize("alpha", codex, host_name="codex")
    (codex / "alpha" / "SKILL.md").write_text(_md("alpha", "first", body="DRIFTED"),
                                              encoding="utf-8")

    def _resolve(h: str):
        return {"claude": claude, "codex": codex}[h]

    issues = check_registry(reg, resolve_host=_resolve)
    drift = [i for i in issues if "differs" in i.message]
    assert len(drift) == 1
    assert drift[0].host == "codex"
    # repair re-materializes the drifted host back into sync
    actions, remaining = repair(reg, resolve_host=_resolve)
    assert any(a.ok and "materialized" in a.action for a in actions)
    assert not any("differs" in i.message for i in remaining)


def test_repair_restores_tampered_file(reg):
    p = reg.skills_root / "alpha" / "versions" / "v1" / "SKILL.md"
    p.write_text(_md("alpha", "first", body="TAMPERED"), encoding="utf-8")
    actions, remaining = repair(reg)
    assert any(a.ok and "git HEAD" in a.action for a in actions)
    assert remaining == []  # re-verified clean
    assert "TAMPERED" not in p.read_text()


def test_repair_restores_missing_file(reg):
    (reg.skills_root / "alpha" / "versions" / "v1" / "SKILL.md").unlink()
    actions, remaining = repair(reg)
    assert any(a.ok for a in actions)
    assert remaining == []


def test_repair_fixes_host_drift(reg, tmp_path):
    host = tmp_path / "host"
    reg.materialize("alpha", host)
    (host / "alpha" / "SKILL.md").write_text(_md("alpha", "first", body="EDITED"), encoding="utf-8")
    actions, remaining = repair(reg, host_dir=host)
    assert any(a.ok and "materialized" in a.action for a in actions)
    assert remaining == []
    assert "EDITED" not in (host / "alpha" / "SKILL.md").read_text()


def test_repair_leaves_dangling_pointer_for_user(reg):
    rec = reg.get("alpha")
    rec.skill.active_version = "v99"
    reg._write(rec)
    actions, remaining = repair(reg)
    # not auto-fixed: no action taken, still reported after re-verify
    assert not actions
    assert any(i.kind == "dangling_active" for i in remaining)

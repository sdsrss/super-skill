import pytest

from super_skill.doctor import DoctorIssue, check_registry
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

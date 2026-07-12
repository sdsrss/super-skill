from super_skill.registry import Registry
from super_skill.seed import seed_from_host


def _make_skill(host, name, desc, body="body"):
    d = host / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n")


def test_seed_imports_valid_skills(tmp_path):
    host = tmp_path / "host"
    _make_skill(host, "alpha", "first")
    _make_skill(host, "beta", "second")
    reg = Registry(root=tmp_path / "state")
    report = seed_from_host(reg, host)
    assert set(report.imported) == {"alpha", "beta"}
    assert {r.skill.skill_id for r in reg.list_skills()} == {"alpha", "beta"}


def test_seed_skips_invalid(tmp_path):
    host = tmp_path / "host"
    _make_skill(host, "good", "ok")
    (host / "nomd").mkdir()  # dir without SKILL.md
    bad = host / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter at all")
    reg = Registry(root=tmp_path / "state")
    report = seed_from_host(reg, host)
    assert report.imported == ["good"]
    skipped = dict(report.skipped)
    assert "nomd" in skipped and "bad" in skipped


def test_seed_is_idempotent(tmp_path):
    host = tmp_path / "host"
    _make_skill(host, "alpha", "first")
    reg = Registry(root=tmp_path / "state")
    seed_from_host(reg, host)
    report2 = seed_from_host(reg, host)
    assert report2.unchanged == ["alpha"]
    assert report2.imported == []
    assert list(reg.get("alpha").versions) == ["v1"]  # no duplicate version


def test_seed_detects_change_as_new_version(tmp_path):
    host = tmp_path / "host"
    _make_skill(host, "alpha", "first")
    reg = Registry(root=tmp_path / "state")
    seed_from_host(reg, host)
    (host / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: changed\n---\nnew body\n"
    )
    report2 = seed_from_host(reg, host)
    assert report2.updated == ["alpha"]
    assert list(reg.get("alpha").versions) == ["v1", "v2"]
    assert reg.get("alpha").skill.active_version == "v2"


def test_seed_does_not_touch_host(tmp_path):
    host = tmp_path / "host"
    _make_skill(host, "alpha", "first")
    before = (host / "alpha" / "SKILL.md").read_text()
    reg = Registry(root=tmp_path / "state")
    seed_from_host(reg, host)
    assert (host / "alpha" / "SKILL.md").read_text() == before
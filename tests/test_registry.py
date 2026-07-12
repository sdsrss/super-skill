import pytest

from super_skill.registry import Registry, RegistryError
from super_skill.schemas import CandidateType, OperationType, ProvenanceKind, SkillStatus


def _md(name: str, desc: str, body: str = "do the thing") -> str:
    return f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n"


@pytest.fixture
def reg(tmp_path):
    r = Registry(root=tmp_path / "state")
    r.init()
    return r


def test_init_creates_git(reg):
    assert (reg.root / ".git").exists()
    assert reg.head() != "(no commits)"


def test_add_version_v1_active(reg):
    sv = reg.add_version(
        "dep-resolver", _md("dep-resolver", "diagnose"),
        CandidateType.DISTILLED, [], actor="seed",
    )
    assert sv.version == "v1"
    rec = reg.get("dep-resolver")
    assert rec is not None
    assert rec.skill.active_version == "v1"
    assert rec.active.artifact_hash.startswith("sha256:")
    assert rec.audit[-1].op == OperationType.PROMOTE


def test_second_version_links_parent(reg):
    reg.add_version("s", _md("s", "v1 desc"), CandidateType.CAPTURED, [])
    sv2 = reg.add_version("s", _md("s", "v2 desc"), CandidateType.FIX, [])
    assert sv2.version == "v2"
    assert sv2.parent_versions == ["v1"]
    assert reg.get("s").skill.active_version == "v2"


def test_rollback_switches_pointer(reg):
    reg.add_version("s", _md("s", "v1"), CandidateType.CAPTURED, [])
    reg.add_version("s", _md("s", "v2"), CandidateType.FIX, [])
    rec = reg.set_active("s", "v1", op=OperationType.ROLLBACK, reason="regressed")
    assert rec.skill.active_version == "v1"
    assert rec.audit[-1].op == OperationType.ROLLBACK
    assert rec.audit[-1].from_version == "v2"


def test_rollback_unknown_version_errors(reg):
    reg.add_version("s", _md("s", "v1"), CandidateType.CAPTURED, [])
    with pytest.raises(RegistryError, match="no version"):
        reg.set_active("s", "v9", op=OperationType.ROLLBACK)


def test_corrupt_meta_raises_registry_error(reg):
    """P1-3 / M12: a truncated/corrupt meta.json must surface as RegistryError,
    not a raw pydantic ValidationError that crashes status/list/doctor."""
    reg.add_version("dep", _md("dep", "x"), CandidateType.CAPTURED, [])
    (reg.skills_root / "dep" / "meta.json").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(RegistryError):
        reg.get("dep")
    with pytest.raises(RegistryError):
        reg.list_skills()


def test_events_and_watermark_gitignored(reg):
    """P2-2 / M9: the capture WAL + mine watermark must not be swept into the
    registry's tracked history by ``git add -A``."""
    (reg.root / "events" / "2026-01-01").mkdir(parents=True)
    (reg.root / "events" / "2026-01-01" / "events.jsonl").write_text("{}\n")
    (reg.root / "mine_state.json").write_text("{}")
    reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])  # triggers git add -A
    ls = reg._git("ls-files")
    assert "events/" not in ls
    assert "mine_state.json" not in ls


def test_gitignore_rebuilt_if_missing(reg):
    """P2-3 / M10: .git present but .gitignore deleted -> init must rebuild it,
    else candidates/ becomes tracked and the One Writer Rule breaks."""
    (reg.root / ".gitignore").unlink()
    reg.init()
    gi = (reg.root / ".gitignore").read_text()
    assert "candidates/" in gi and "events/" in gi


def test_add_version_identical_to_active_is_noop(reg):
    """P1-4 / M8: re-adding content identical to the active version must not
    create a new node (crash-idempotent promotion)."""
    raw = _md("s", "same")
    sv1 = reg.add_version("s", raw, CandidateType.CAPTURED, [])
    sv2 = reg.add_version("s", raw, CandidateType.CAPTURED, [])
    assert sv2.version == sv1.version
    assert list(reg.get("s").versions) == ["v1"]


def test_make_active_false_keeps_pointer(reg):
    reg.add_version("s", _md("s", "v1"), CandidateType.CAPTURED, [])
    reg.add_version("s", _md("s", "cand"), CandidateType.FIX, [], make_active=False)
    rec = reg.get("s")
    assert rec.skill.active_version == "v1"
    assert set(rec.versions) == {"v1", "v2"}


def test_version_text_roundtrip(reg):
    raw = _md("s", "desc", body="unique-body-marker")
    reg.add_version("s", raw, CandidateType.CAPTURED, [])
    assert "unique-body-marker" in reg.version_text("s", "v1")


def test_list_returns_all(reg):
    reg.add_version("a", _md("a", "d"), CandidateType.DISTILLED, [])
    reg.add_version("b", _md("b", "d"), CandidateType.DISTILLED, [])
    ids = {r.skill.skill_id for r in reg.list_skills()}
    assert ids == {"a", "b"}


def test_provenance_kind_persisted(reg):
    from super_skill.schemas import Provenance

    prov = [Provenance(kind=ProvenanceKind.SEED_EXISTING_SKILL, origin="/x/SKILL.md")]
    reg.add_version("s", _md("s", "d"), CandidateType.DISTILLED, prov, status=SkillStatus.ACTIVE)
    assert reg.get("s").active.provenance[0].kind == ProvenanceKind.SEED_EXISTING_SKILL

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


def test_commit_failure_raises_registry_error(reg, monkeypatch):
    """P3-1 / audit L15: a failed git commit must surface as RegistryError (which
    the CLI catches), not a raw CalledProcessError traceback."""
    import subprocess

    from super_skill import registry as reg_mod

    real = subprocess.run

    def fake(cmd, *a, **k):
        if "commit" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "fatal: commit failed")
        return real(cmd, *a, **k)

    monkeypatch.setattr(reg_mod.subprocess, "run", fake)
    with pytest.raises(RegistryError, match="commit"):
        reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])


def test_meta_json_mode_is_owner_only(reg):
    """P1-3 / audit P2-1: meta.json carries session-derived provenance/audit — it
    must not be world/group-readable on a shared host."""
    import stat

    reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])
    mode = stat.S_IMODE(reg._meta_path("s").stat().st_mode)
    assert mode & 0o077 == 0, oct(mode)


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


# --- P3-4: schema_version + read-side forward tolerance -----------------------

def test_meta_json_stamped_with_schema_version(reg):
    """P3-4 / audit N3: every persisted meta.json carries a schema_version so a
    future reader can detect version skew instead of guessing."""
    import json

    from super_skill.schemas import SCHEMA_VERSION

    reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])
    meta = json.loads((reg.skills_root / "s" / "meta.json").read_text())
    assert meta["schema_version"] == SCHEMA_VERSION


def test_get_tolerates_unknown_future_fields(reg):
    """P3-4 / audit N3: an older CLI reading a meta.json written by a newer
    super-skill (extra top-level + extra per-version fields, higher
    schema_version) must degrade gracefully, not die with 'corrupt meta.json'."""
    import json

    reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])
    p = reg.skills_root / "s" / "meta.json"
    meta = json.loads(p.read_text())
    meta["schema_version"] = 99  # written by a much newer super-skill
    meta["future_top_level"] = {"whatever": 1}
    meta["versions"]["v1"]["future_field"] = "ignored"
    meta["skill"]["future_skill_field"] = True
    p.write_text(json.dumps(meta), encoding="utf-8")
    rec = reg.get("s")  # must NOT raise RegistryError
    assert rec is not None
    assert rec.skill.active_version == "v1"


# --- P2-5: materialized-host tracking -----------------------------------------

def test_materialize_records_host(reg, tmp_path):
    """P2-5 / audit P2-6: the registry must record which hosts a skill was
    distributed to, so rollback/doctor can re-sync/verify every one of them."""
    reg.add_version("s", _md("s", "d"), CandidateType.CAPTURED, [])
    reg.materialize("s", tmp_path / "claude", host_name="claude")
    reg.materialize("s", tmp_path / "codex", host_name="codex")
    assert reg.get("s").skill.materialized_hosts == ["claude", "codex"]
    # idempotent: re-materializing to a known host does not duplicate it
    reg.materialize("s", tmp_path / "claude", host_name="claude")
    assert reg.get("s").skill.materialized_hosts == ["claude", "codex"]


# --- P2-6: cross-writer lock (no lost update under concurrent add_version) -----

def test_concurrent_add_version_no_lost_update(reg, monkeypatch):
    """P2-6 / audit P2-7: two writers promoting the same skill concurrently must
    both land (v1 + v2). Without an inter-writer lock the read-modify-write of
    meta.json races and one promotion is silently clobbered. A delay is injected
    between the get() and the write to force the interleave deterministically."""
    import threading
    import time

    from super_skill import registry as reg_mod

    real_hash = reg_mod.content_hash
    slow = {"armed": True}

    def _slow_hash(raw: str) -> str:
        # Widen the read-modify-write window exactly once so both writers would
        # collide on v1 absent the lock.
        if slow["armed"]:
            slow["armed"] = False
            time.sleep(0.15)
        return real_hash(raw)

    monkeypatch.setattr(reg_mod, "content_hash", _slow_hash)
    root = reg.root
    barrier = threading.Barrier(2)

    def _writer(tag: str) -> None:
        r = Registry(root=root)
        barrier.wait()
        r.add_version("s", _md("s", tag), CandidateType.CAPTURED, [])

    threads = [threading.Thread(target=_writer, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    versions = list(reg.get("s").versions)
    assert versions == ["v1", "v2"], f"lost update: only {versions}"


def test_init_refuses_foreign_git_history(tmp_path):
    """Audit P0-1 defense-in-depth: pointing SUPER_SKILL_HOME at an existing
    (non-registry) git repo must refuse, not adopt it — init used to overwrite
    .gitignore and `git add -A` commit the user's uncommitted work."""
    import subprocess

    from super_skill.registry import Registry, RegistryError

    repo = tmp_path / "user-repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "work.txt").write_text("precious uncommitted work", encoding="utf-8")
    (repo / ".gitignore").write_text("# user's own ignore rules\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=u@x", "-c", "user.name=u",
         "commit", "-qm", "user work"],
        check=True,
    )
    import pytest as _pytest

    with _pytest.raises(RegistryError, match="refusing to adopt"):
        Registry(root=repo).init()
    # nothing was touched: user's .gitignore intact, no registry commit
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "# user's own ignore rules\n"
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%s"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "super-skill" not in log


def test_init_adopts_own_registry_history(tmp_path):
    """Re-running init on a registry super-skill itself created stays idempotent."""
    from super_skill.registry import Registry

    reg = Registry(root=tmp_path / "state")
    reg.init()
    reg.init()  # second run must not raise

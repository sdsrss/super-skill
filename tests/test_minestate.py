from super_skill import minestate
from super_skill.capture import EventLog
from super_skill.schemas import EventType


def test_watermark_absent_reads_empty(tmp_path):
    root = tmp_path / "state"
    assert minestate.mined_sessions(root) == set()


def test_watermark_roundtrip(tmp_path):
    root = tmp_path / "state"
    minestate.record_mined(root, {"s1", "s2"})
    assert minestate.mined_sessions(root) == {"s1", "s2"}
    minestate.record_mined(root, {"s1", "s2", "s3"})  # overwrites, not appends
    assert minestate.mined_sessions(root) == {"s1", "s2", "s3"}


def test_unmined_counts_sessions_not_yet_mined(tmp_path):
    root = tmp_path / "state"
    assert minestate.unmined(root, {"s1", "s2"}) == 2  # nothing mined yet
    minestate.record_mined(root, {"s1", "s2"})
    assert minestate.unmined(root, {"s1", "s2"}) == 0
    assert minestate.unmined(root, {"s1", "s2", "s3"}) == 1  # s3 is new


def test_unmined_robust_to_wal_pruning(tmp_path):
    """P2-5 / M13: after TTL pruning drops old mined sessions, NEW sessions must
    still count as unmined — the old absolute-count watermark went silent here."""
    root = tmp_path / "state"
    minestate.record_mined(root, {"s1", "s2", "s3"})
    # WAL pruned: s1,s2 rolled off; s4,s5 are new arrivals
    assert minestate.unmined(root, {"s3", "s4", "s5"}) == 2


def test_corrupt_state_reads_empty(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    (root / "mine_state.json").write_text("not json at all")
    assert minestate.mined_sessions(root) == set()


def test_reminder_threshold_env(monkeypatch):
    monkeypatch.delenv("SUPER_SKILL_MINE_REMINDER", raising=False)
    assert minestate.reminder_threshold() == 20
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "5")
    assert minestate.reminder_threshold() == 5


def test_distinct_sessions_dedupes(tmp_path):
    root = tmp_path / "state"
    log = EventLog(root)
    for sid in ("s1", "s1", "s2", "s3", "s3"):
        log.append(EventType.USER_PROMPT_SUBMIT, sid, {"text": "hi"})
    assert log.distinct_sessions() == 3


def test_default_threshold_is_20():
    """Audit follow-up: 3 re-fired at nearly every session for a heavy user;
    default raised to 20 (env-overridable)."""
    assert minestate.reminder_threshold() == 20


def test_reminder_due_zero_disables(monkeypatch):
    """SUPER_SKILL_MINE_REMINDER=0 means 'reminder off', not 'always fire'
    (audit P2-13: 0 used to make an un-clearable perpetual nag)."""
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "0")
    assert minestate.reminder_due(10_000) is False


def test_reminder_due_at_threshold(monkeypatch):
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "5")
    assert minestate.reminder_due(4) is False
    assert minestate.reminder_due(5) is True


def test_reminder_threshold_invalid_or_negative_defaults(monkeypatch, capsys):
    """Numeric-knob consistency (audit P2-14): invalid values warn and default
    instead of silently defaulting (EVENT_TTL already behaves this way)."""
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "abc")
    assert minestate.reminder_threshold() == 20
    assert "SUPER_SKILL_MINE_REMINDER" in capsys.readouterr().err
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "-4")
    assert minestate.reminder_threshold() == 20

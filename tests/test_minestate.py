from super_skill import minestate
from super_skill.capture import EventLog
from super_skill.schemas import EventType


def test_watermark_absent_reads_zero(tmp_path):
    root = tmp_path / "state"
    assert minestate.mined_sessions(root) == 0


def test_watermark_roundtrip(tmp_path):
    root = tmp_path / "state"
    minestate.record_mined(root, 5)
    assert minestate.mined_sessions(root) == 5
    minestate.record_mined(root, 9)  # overwrites, not appends
    assert minestate.mined_sessions(root) == 9


def test_unmined_is_current_minus_watermark(tmp_path):
    root = tmp_path / "state"
    assert minestate.unmined(root, 4) == 4  # nothing mined yet
    minestate.record_mined(root, 4)
    assert minestate.unmined(root, 4) == 0
    assert minestate.unmined(root, 7) == 3
    # watermark ahead of current (WAL pruned since last mine) clamps to 0
    assert minestate.unmined(root, 2) == 0


def test_corrupt_state_reads_zero(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    (root / "mine_state.json").write_text("not json at all")
    assert minestate.mined_sessions(root) == 0


def test_reminder_threshold_env(monkeypatch):
    monkeypatch.delenv("SUPER_SKILL_MINE_REMINDER", raising=False)
    assert minestate.reminder_threshold() == 3
    monkeypatch.setenv("SUPER_SKILL_MINE_REMINDER", "5")
    assert minestate.reminder_threshold() == 5


def test_distinct_sessions_dedupes(tmp_path):
    root = tmp_path / "state"
    log = EventLog(root)
    for sid in ("s1", "s1", "s2", "s3", "s3"):
        log.append(EventType.USER_PROMPT_SUBMIT, sid, {"text": "hi"})
    assert log.distinct_sessions() == 3

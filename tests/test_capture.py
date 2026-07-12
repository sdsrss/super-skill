from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from super_skill.capture import EventLog
from super_skill.mine import mine_families
from super_skill.schemas import EventType


def _proc_append(args):
    """Top-level (picklable) worker for the cross-process concurrency test."""
    root, i = args
    EventLog(root=root).append(EventType.POST_TOOL_USE, f"s{i % 4}", {"i": i, "blob": "y" * 30000})


def test_append_and_iter(tmp_path):
    log = EventLog(root=tmp_path)
    ev = log.append(EventType.PRE_TOOL_USE, "s1", {"tool": "pytest"})
    assert ev.event_id
    assert log.count() == 1
    got = next(iter(log.iter_events()))
    assert got.event_type == EventType.PRE_TOOL_USE
    assert got.payload["tool"] == "pytest"


def test_secret_never_written_to_disk(tmp_path):
    """The load-bearing guarantee: a secret in a payload must not appear in the
    on-disk WAL (FR-CAP-2, §8 SAFETY)."""
    log = EventLog(root=tmp_path)
    secret = "sk-DEADBEEF0123456789abcdefghij"
    log.append(EventType.POST_TOOL_USE, "s1", {"stdout": f"API key is {secret}"})

    wal_files = list((tmp_path / "events").rglob("events.jsonl"))
    assert wal_files, "no WAL written"
    on_disk = wal_files[0].read_text()
    assert secret not in on_disk
    assert "REDACTED:openai_key" in on_disk


def test_iter_events_skips_corrupt_line(tmp_path):
    """P0-3 / H3: a torn/partial line (killed hook mid-append) must not brick the
    reader — bad lines are skipped, valid records still read."""
    log = EventLog(root=tmp_path)
    log.append(EventType.STOP, "s1", {"tool": "pytest"})
    wal = next((tmp_path / "events").rglob("events.jsonl"))
    with wal.open("a", encoding="utf-8") as f:
        f.write('{"event_id":"partial","sess')  # torn final line, no newline
    # every reader must survive
    assert log.count() == 1
    got = list(log.iter_events())
    assert len(got) == 1 and got[0].session_id == "s1"
    assert log.distinct_sessions() == 1


def test_concurrent_appends_stay_intact(tmp_path):
    """P0-4 / H4: concurrent appends of large payloads must not interleave into a
    corrupt line. Each append is one atomic write."""
    log = EventLog(root=tmp_path)
    big = "x" * 20000  # exceeds the buffered-writer chunk size

    def worker(i: int) -> None:
        log.append(EventType.POST_TOOL_USE, f"s{i % 4}", {"i": i, "blob": big})

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(worker, range(80)))
    # all 80 lines must parse (no interleaving) and none lost
    assert log.count() == 80


def test_concurrent_appends_across_processes(tmp_path):
    """P4-4 / H4: true multi-process concurrency (no GIL) — cross-process
    O_APPEND appends of large payloads must not interleave or lose lines."""
    log = EventLog(root=tmp_path)
    n = 60
    with ProcessPoolExecutor(max_workers=6) as ex:
        list(ex.map(_proc_append, [(tmp_path, i) for i in range(n)]))
    assert log.count() == n  # every line parsed -> no torn/interleaved records


def test_project_id_home_path_redacted(tmp_path):
    """project_id derives from cwd (a home path) and must not leak to disk."""
    log = EventLog(root=tmp_path)
    log.append(EventType.SESSION_START, "s1", {}, project_id="/home/alice/secret-proj")
    on_disk = (tmp_path / "events").rglob("events.jsonl").__next__().read_text()
    assert "/home/alice" not in on_disk
    ev = next(iter(log.iter_events()))
    assert ev.project_id is not None and ev.project_id.startswith("~")


def test_redaction_marks_persisted(tmp_path):
    log = EventLog(root=tmp_path)
    ev = log.append(EventType.USER_PROMPT_SUBMIT, "s1", {"text": "email me@example.com"})
    assert any(m.kind == "email" for m in ev.redactions)


def test_events_partitioned_by_day(tmp_path):
    log = EventLog(root=tmp_path)
    log.append(EventType.STOP, "s1", {})
    days = [p.name for p in (tmp_path / "events").iterdir()]
    assert len(days) == 1
    assert days[0].count("-") == 2  # yyyy-mm-dd


def test_mine_surfaces_recurring_family(tmp_path):
    log = EventLog(root=tmp_path)
    # same "dependency resolution" workflow across 3 distinct sessions
    for sid in ("s1", "s2", "s3"):
        log.append(EventType.USER_PROMPT_SUBMIT, sid,
                   {"text": "dependency resolution failure in lockfile"})
    # a one-off in a single session must not surface
    log.append(EventType.USER_PROMPT_SUBMIT, "s9", {"text": "rename a variable"})

    families = mine_families(log.iter_events(), min_sessions=3)
    labels = {f.label for f in families}
    assert any("dependency" in lbl or "resolution" in lbl or "lockfile" in lbl for lbl in labels)
    assert all(f.session_count >= 3 for f in families)


def test_mine_strips_harness_notification_envelope(tmp_path):
    """Task-notification boilerplate (summary/note/ids/output-file/usage metrics)
    is harness metadata, not task content — it dominated real mining output
    (8 sessions / 31 events of pure template prose on 2026-07-12). It must not
    mine into families, while content inside <result> still must."""
    log = EventLog(root=tmp_path)
    boiler = (
        '<task-notification task-id="abc123">'
        '<summary>Agent "Review detection" finished</summary>\n'
        "<note>A task-notification fires each time this agent stops with no live "
        "background children of its own. The user can send it another message and "
        "resume it, so the same task-id may notify more than once.</note>\n"
        "<tool-use-id>toolu_01ABCDEF</tool-use-id>\n"
        "<output-file>/tmp/tasks/abc123.output</output-file>\n"
        "<result>release tag push sequence verified clean</result>"
        "</task-notification>\n"
        "usage: subagent_tokens=512 tool_uses=5 duration_ms=1000"
    )
    for sid in ("s1", "s2", "s3"):
        log.append(EventType.STOP, sid, {"last_assistant_message": boiler})
    labels = " ".join(f.label for f in mine_families(log.iter_events(), min_sessions=3))
    for meta in (
        "task-notification",
        "task-id",
        "tool-use-id",
        "output-file",
        "subagent_tokens",
        "tool_uses",
        "duration_ms",
        "another message",
        "can send",
        "notify",
    ):
        assert meta not in labels, f"harness metadata mined: {meta}"
    assert "tag push" in labels  # <result> content still mines


def test_mine_empty(tmp_path):
    assert mine_families(EventLog(root=tmp_path).iter_events()) == []


def test_mine_below_session_threshold_is_empty(tmp_path):
    """A family recurring in only 2 sessions must not surface at min_sessions=3."""
    log = EventLog(root=tmp_path)
    for sid in ("s1", "s2"):  # two distinct sessions only
        log.append(EventType.USER_PROMPT_SUBMIT, sid, {"text": "flaky retry pipeline stall"})
    assert mine_families(log.iter_events(), min_sessions=3) == []
    # lowering the threshold to 2 surfaces it
    assert mine_families(log.iter_events(), min_sessions=2)


def test_mine_ignores_envelope_and_redaction_noise(tmp_path):
    """Coarse mining must surface task content, not the hook envelope (event name,
    session id, cwd) or redaction placeholders — those produce junk families."""
    log = EventLog(root=tmp_path)
    for sid in ("s1", "s2", "s3"):
        log.append(
            EventType.USER_PROMPT_SUBMIT,
            sid,
            {
                # envelope fields the CLI dumps wholesale into payload:
                "hook_event_name": "UserPromptSubmit",
                "session_id": sid,
                "cwd": "/home/sds/secret-proj",
                # real content + a secret that gets redacted in place:
                "text": "flaky retry loop in the pipeline",
                "note": "key sk-DEADBEEF0123456789abcdefghij here",
            },
        )
    labels = " ".join(f.label for f in mine_families(log.iter_events(), min_sessions=3))
    # envelope / metadata must not appear as mined tokens
    assert "userpromptsubmit" not in labels
    assert "session" not in labels
    assert "secret-proj" not in labels  # cwd-derived slug
    # redaction placeholder + kind name must not leak as tokens
    assert "redacted" not in labels
    assert "openai" not in labels
    # real content still mines
    assert any(w in labels for w in ("flaky", "retry", "pipeline"))

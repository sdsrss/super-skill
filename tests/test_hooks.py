"""Claude Code hooks config generation (docs/03 WS: day-1 capture)."""

import json

from super_skill.hooks import ALL_EVENTS, hooks_settings


def test_all_six_host_events_wired():
    settings = hooks_settings()
    assert set(settings["hooks"]) == set(ALL_EVENTS)
    assert len(ALL_EVENTS) == 6


def test_tool_events_have_matcher():
    hooks = hooks_settings()["hooks"]
    # PreToolUse/PostToolUse fire per-tool -> need a matcher; the rest do not
    assert hooks["PreToolUse"][0]["matcher"] == "*"
    assert hooks["PostToolUse"][0]["matcher"] == "*"
    assert "matcher" not in hooks["UserPromptSubmit"][0]


def test_every_event_runs_capture():
    for entries in hooks_settings()["hooks"].values():
        cmd = entries[0]["hooks"][0]
        assert cmd["type"] == "command"
        assert "capture" in cmd["command"]


def test_custom_command_threaded_through():
    hooks = hooks_settings(command="/opt/ss capture")["hooks"]
    assert hooks["Stop"][0]["hooks"][0]["command"] == "/opt/ss capture"


def test_output_is_json_serializable():
    json.dumps(hooks_settings())  # must not raise


def test_session_start_also_wires_status_reminder():
    """SessionStart carries a second entry (matcher=startup) running the
    status-reminder command, so fresh sessions surface the mine backlog."""
    entries = hooks_settings()["hooks"]["SessionStart"]
    reminder = [
        e
        for e in entries
        if any("status-reminder" in h["command"] for h in e["hooks"])
    ]
    assert len(reminder) == 1
    assert reminder[0]["matcher"] == "startup"


def test_reminder_command_follows_custom_command_prefix():
    entries = hooks_settings(command="/opt/ss capture")["hooks"]["SessionStart"]
    cmds = [h["command"] for e in entries for h in e["hooks"]]
    assert "/opt/ss status-reminder" in cmds

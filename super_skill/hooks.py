"""Claude Code hooks config generation (docs/03 WS: capture from day 1).

Produces the ``hooks`` block that wires the six host events to
``super-skill capture`` so real sessions accumulate into the WAL. We only
*generate* the config — writing it into ``~/.claude/settings.json`` is the
user's call (user-global config is §5 hard-AUTH), so ``super-skill hooks-config``
prints it for the user to merge, rather than editing settings behind their back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import minestate
from .capture import EventLog

# Events without a per-tool matcher fire once; PreToolUse/PostToolUse fire
# per tool call and take a matcher.
_EVENTS_NO_MATCHER = ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")
_EVENTS_WITH_MATCHER = ("PreToolUse", "PostToolUse")
ALL_EVENTS = _EVENTS_NO_MATCHER + _EVENTS_WITH_MATCHER

DEFAULT_COMMAND = "super-skill capture"


def _reminder_command(capture_command: str) -> str:
    """Sibling ``status-reminder`` invocation for a given capture command."""
    return capture_command.removesuffix(" capture") + " status-reminder"


def hooks_settings(command: str = DEFAULT_COMMAND) -> dict[str, Any]:
    """Return a settings.json fragment: every host event piped to ``command``.

    capture reads the hook JSON on stdin and never fails the session (NFR-3).
    SessionStart additionally wires the ``status-reminder`` helper (matcher
    ``startup``) so a fresh session surfaces the unmined backlog to the user."""
    run = {"hooks": [{"type": "command", "command": command}]}
    hooks: dict[str, list[dict[str, Any]]] = {}
    for ev in _EVENTS_NO_MATCHER:
        hooks[ev] = [dict(run)]
    for ev in _EVENTS_WITH_MATCHER:
        hooks[ev] = [{"matcher": "*", **run}]
    hooks["SessionStart"].append(
        {
            "matcher": "startup",
            "hooks": [
                {
                    "type": "command",
                    "command": _reminder_command(command),
                    "timeout": 10,
                }
            ],
        }
    )
    return {"hooks": hooks}


def status_reminder_json(root: Path) -> str | None:
    """SessionStart envelope carrying the unmined-sessions reminder, or None
    when the backlog is below the nudge threshold.

    Envelope rules (SessionStart is a receipt event): JSON hookSpecificOutput,
    injected prose carries explicit not-user-input framing plus a continue
    instruction so the model relays it without derailing the user's task."""
    log = EventLog(root)
    n = minestate.unmined(root, log.session_ids())
    if n < minestate.reminder_threshold():
        return None
    text = (
        f"[super-skill] {n} distinct captured sessions are unmined — run "
        "`super-skill mine`. || System-injected reminder, NOT a user message. "
        "Early in this session, proactively tell the user (in their language) "
        "that captured coding sessions have accumulated unmined, show the "
        "command `super-skill mine`, and directly offer to run it for them "
        "now (a simple yes/no). Then continue with the user's actual task."
    )
    return json.dumps(
        {
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            },
        }
    )

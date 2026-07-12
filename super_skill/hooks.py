"""Claude Code hooks config generation (docs/03 WS: capture from day 1).

Produces the ``hooks`` block that wires the six host events to
``super-skill capture`` so real sessions accumulate into the WAL. We only
*generate* the config — writing it into ``~/.claude/settings.json`` is the
user's call (user-global config is §5 hard-AUTH), so ``super-skill hooks-config``
prints it for the user to merge, rather than editing settings behind their back.
"""

from __future__ import annotations

from typing import Any

# Events without a per-tool matcher fire once; PreToolUse/PostToolUse fire
# per tool call and take a matcher.
_EVENTS_NO_MATCHER = ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")
_EVENTS_WITH_MATCHER = ("PreToolUse", "PostToolUse")
ALL_EVENTS = _EVENTS_NO_MATCHER + _EVENTS_WITH_MATCHER

DEFAULT_COMMAND = "super-skill capture"


def hooks_settings(command: str = DEFAULT_COMMAND) -> dict[str, Any]:
    """Return a settings.json fragment: every host event piped to ``command``.

    capture reads the hook JSON on stdin and never fails the session (NFR-3)."""
    run = {"hooks": [{"type": "command", "command": command}]}
    hooks: dict[str, list[dict[str, Any]]] = {}
    for ev in _EVENTS_NO_MATCHER:
        hooks[ev] = [dict(run)]
    for ev in _EVENTS_WITH_MATCHER:
        hooks[ev] = [{"matcher": "*", **run}]
    return {"hooks": hooks}

"""Regex redaction (WS degraded form of FR-CAP-2).

Runs BEFORE anything is written to the WAL: secret VALUES never reach disk — only
the kind and the field where one was found are recorded (FR-CAP-2, §8 SAFETY).
This is the WS regex pass; the full M2 double-redaction + allowlist is later.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

from .schemas import RedactionMark

_HOME = os.path.expanduser("~")

# (kind, pattern, group). Ordered specific -> generic; earlier wins on overlap.
# group 0 = redact whole match; group N = redact only that capture, keep context.
_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("private_key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ), 0),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"), 0),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}"), 0),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), 0),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), 0),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), 0),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*"), 0),
    ("assigned_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key)\b"
        r"\s*[:=]\s*['\"]?([^\s'\"]{6,})",
    ), 1),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 0),
]

# Private home path -> ~ (not a secret, but FR-CAP-2 lists 私有路径).
_HOME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(re.escape(_HOME)),
    re.compile(r"/home/[^/\s'\"]+"),
    re.compile(r"/Users/[^/\s'\"]+"),
]


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, {kind: count}). Secret values are replaced with a
    ``[REDACTED:kind]`` token; home paths collapse to ``~``."""
    counts: dict[str, int] = {}

    def _make_repl(kind: str, group: int, token: str) -> Callable[[re.Match[str]], str]:
        def _r(m: re.Match[str]) -> str:
            counts[kind] = counts.get(kind, 0) + 1
            return token if group == 0 else m.group(0).replace(m.group(group), token)

        return _r

    for kind, pat, group in _PATTERNS:
        text = pat.sub(_make_repl(kind, group, f"[REDACTED:{kind}]"), text)

    # home paths collapse to ~ (private path, not a secret value)
    for pat in _HOME_PATTERNS:
        text = pat.sub(_make_repl("home_path", 0, "~"), text)

    return text, counts


def redact_payload(obj: Any, _path: str = "") -> tuple[Any, list[RedactionMark]]:
    """Recursively redact all string leaves in a JSON-like structure, collecting
    marks that record kind + dotted field path (never the value)."""
    marks: list[RedactionMark] = []
    if isinstance(obj, str):
        red, counts = redact_text(obj)
        marks.extend(
            RedactionMark(kind=k, location=_path or "(root)", count=c)
            for k, c in counts.items()
        )
        return red, marks
    if isinstance(obj, dict):
        out_d: dict[str, Any] = {}
        for k, v in obj.items():
            child = f"{_path}.{k}" if _path else str(k)
            out_d[k], sub = redact_payload(v, child)
            marks.extend(sub)
        return out_d, marks
    if isinstance(obj, list):
        out_l: list[Any] = []
        for i, v in enumerate(obj):
            child = f"{_path}[{i}]"
            rv, sub = redact_payload(v, child)
            out_l.append(rv)
            marks.extend(sub)
        return out_l, marks
    return obj, marks

"""Instruction-layer adversarial gate (docs/04 §2.4bis) — WS rule-based form.

v1's ONLY mandatory security gate. v1 candidates are pure text with no scripts,
so the host Agent treats the SKILL.md body + description as TRUSTED instructions
and runs them in the user's real session — outside any sandbox, with full
credentials. A poisoned imperative distilled from captured content (dependency
errors, READMEs, issues, web pages) is exactly the code×instruction seam that
MalSkillBench shows single-tool scanners miss.

This pass scans body + description for external-action imperatives. Per §2.4bis a
T1 pure-text skill needs *higher*, not lower, injection scrutiny, so it errs
toward flagging: a false positive costs one human edit; a miss ships a
`curl | bash` to the host. The cross-modal (script↔manifest) and LLM-judge layers
land at M1 — v1 candidates carry no scripts, so there is nothing to cross-check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .skillmd import parse

# (category, pattern). Case-insensitive. Ordered most-severe first.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "pipe_to_shell",
        re.compile(
            r"(?i)\b(?:curl|wget|fetch)\b[^\n|]{0,200}\|\s*"
            r"(?:bash|sh|zsh|python3?|node|ruby|perl|eval)\b"
        ),
    ),
    (
        "run_undeclared_script",
        re.compile(
            r"(?i)\beval\s*\(|\bexec\s*\(|\bos\.system\b|\bsubprocess\.\w+"
            r"|\bchmod\s+\+x\b|\bsudo\b|\bnpx\s+\S|"
            r"(?:run|execute)\s+(?:this|the\s+following|the\s+attached)\s+\w*\s*script"
        ),
    ),
    (
        "credential_access",
        re.compile(
            r"(?i)~/\.ssh|~/\.aws|\bid_rsa\b|\.env\b|\bprivate[_-]?key\b"
            r"|\b(?:API[_-]?KEY|SECRET[_-]?KEY|ACCESS[_-]?KEY|AWS_SECRET_ACCESS_KEY)\b"
            r"|\b(?:password|passwd)\b"
        ),
    ),
    (
        "network_fetch",
        re.compile(
            r"(?i)\b(?:curl|wget)\b"
            r"|\b(?:download|fetch|retrieve)\b[^\n]{0,60}https?://"
        ),
    ),
    (
        "prompt_injection_override",
        re.compile(
            r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)"
            r"|disregard\s+(?:the\s+)?(?:above|previous|prior)"
            r"|forget\s+(?:all\s+)?(?:previous|prior)"
            r"|you\s+are\s+now\b|override\s+[^\n]{0,40}instructions"
        ),
    ),
]


@dataclass(frozen=True)
class Finding:
    category: str
    location: str  # "description" | "body"
    snippet: str


class InstructionGateError(RuntimeError):
    """Raised when the gate blocks a promotion. Carries the findings so callers
    can report exactly what tripped it."""

    def __init__(self, findings: list[Finding]) -> None:
        self.findings = findings
        cats = ", ".join(sorted({f.category for f in findings}))
        super().__init__(f"instruction-layer gate blocked: {cats}")


def scan_text(text: str, location: str) -> list[Finding]:
    findings: list[Finding] = []
    for category, pat in _RULES:
        for m in pat.finditer(text):
            snippet = " ".join(m.group(0).split())[:80]
            findings.append(Finding(category=category, location=location, snippet=snippet))
    return findings


def scan_skill_md(raw: str) -> list[Finding]:
    """Scan a SKILL.md's description + body for external-action imperatives.

    description is scanned separately: §2.4bis forbids imperative / second-person
    external-action language there (it would both win routing and inject)."""
    parsed = parse(raw)
    return scan_text(parsed.frontmatter.description, "description") + scan_text(
        parsed.body, "body"
    )

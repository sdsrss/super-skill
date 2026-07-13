"""eval-lite: the deterministic hard-gate layer (docs/04 §1.6, FR-EVAL-2).

At personal scale (n=1–3, corpus <~150 cases) the deterministic layer is THE
hard gate; the statistical layer (precision/recall, +5pp, bootstrap CI) is
diagnostic only and needs a real corpus, so it is not run here. The four-arm
protocol degrades to a No Skill / Skill two-arm — and at WS there is neither a
golden corpus nor an agent harness to run it, so that arm is honestly labelled
``Insufficient Evidence`` rather than skipped or faked (docs/04 §1.6 统计诚实).

What is checked here, without an LLM: structure/schema, zero credential/PII leak
in the SKILL.md text, and the agentskills body token budget. The instruction
gate (§2.4bis) is a separate hard gate run first in ``candidate.approve``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from .redact import redact_text
from .skillmd import SkillMdError, parse

# agentskills.io: SKILL.md body should stay under ~5000 tokens. We have no
# tokenizer at WS, so approximate (~0.75 words/token) — deliberately conservative.
TOKEN_BUDGET = 5000
_WORDS_PER_TOKEN = 0.75
# CJK text has no spaces, so whitespace word-counting scored a whole Chinese body
# as ~1 token and a huge SKILL.md sailed under budget (P0-1). Count CJK chars
# individually at ~1.5 chars/token.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿぀-ゟ゠-ヿ]")
_CJK_CHARS_PER_TOKEN = 1.5


@dataclass(frozen=True)
class EvalCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EvalReport:
    checks: list[EvalCheck] = field(default_factory=list)
    # The No Skill/Skill two-arm needs a corpus + harness we do not have at WS.
    insufficient_evidence: bool = True

    @property
    def passed(self) -> bool:
        """Deterministic hard gate: every check must pass (一票否决)."""
        return all(c.passed for c in self.checks)

    def failures(self) -> list[EvalCheck]:
        return [c for c in self.checks if not c.passed]


class EvalError(RuntimeError):
    """Raised when the deterministic gate fails. Carries the report."""

    def __init__(self, report: EvalReport) -> None:
        self.report = report
        names = ", ".join(c.name for c in report.failures())
        super().__init__(f"eval-lite deterministic gate failed: {names}")


def _approx_tokens(text: str) -> int:
    cjk = len(_CJK_RE.findall(text))
    words = len(re.findall(r"\S+", _CJK_RE.sub(" ", text)))
    return int(words / _WORDS_PER_TOKEN + cjk / _CJK_CHARS_PER_TOKEN)


def eval_lite(raw: str) -> EvalReport:
    """Run the deterministic hard-gate checks on a candidate SKILL.md."""
    checks: list[EvalCheck] = []

    # 1. structure / schema
    try:
        parsed = parse(raw)
        checks.append(EvalCheck("schema", True, "frontmatter valid"))
    except SkillMdError as e:
        return EvalReport(checks=[EvalCheck("schema", False, str(e))])

    # 2. zero credential / PII leak in the instruction text (凭据与 PII 泄漏 = 0).
    # Scan the FULL frontmatter (extra="allow" ships every field to the host, M6),
    # not just description + body. YAML (not JSON) keeps ``keyword: value``
    # adjacency so a secret in a keyword-named field is caught (v0.11.1 #4).
    fm = yaml.safe_dump(
        parsed.frontmatter.model_dump(), default_flow_style=False, allow_unicode=True
    )
    text = f"{fm}\n{parsed.body}"
    _, counts = redact_text(text)
    leaks = {k: c for k, c in counts.items() if k != "home_path"}
    checks.append(
        EvalCheck(
            "no_secret_leak",
            not leaks,
            "clean" if not leaks else f"found {leaks}",
        )
    )

    # 3. agentskills body token budget
    tok = _approx_tokens(parsed.body)
    checks.append(
        EvalCheck("token_budget", tok < TOKEN_BUDGET, f"~{tok} tokens (limit {TOKEN_BUDGET})")
    )

    return EvalReport(checks=checks, insufficient_evidence=True)

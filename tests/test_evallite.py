"""eval-lite deterministic hard-gate layer (docs/04 §1.6, FR-EVAL-2)."""

from super_skill.evallite import EvalError, EvalReport, eval_lite


def _md(body: str, desc: str = "resolve dependency lockfile drift") -> str:
    return f"---\nname: s\ndescription: {desc}\n---\n{body}\n"


def test_clean_candidate_passes_deterministic_gate():
    report = eval_lite(_md("Run the resolver, read the conflict, pin the version."))
    assert isinstance(report, EvalReport)
    assert report.passed
    assert {c.name for c in report.checks} >= {"schema", "no_secret_leak", "token_budget"}


def test_two_arm_marked_insufficient_evidence():
    """No corpus + no agent harness at WS -> the No Skill/Skill two-arm cannot be
    run; it must be labelled, not silently skipped or faked (docs/04 §1.6)."""
    report = eval_lite(_md("harmless body"))
    assert report.insufficient_evidence is True


def test_secret_value_in_body_fails_gate():
    report = eval_lite(_md("export KEY=sk-DEADBEEF0123456789abcdefghij and go"))
    assert not report.passed
    assert any(c.name == "no_secret_leak" and not c.passed for c in report.checks)


def test_secret_in_extra_frontmatter_field_fails_gate():
    """P1-2 / M6: a secret in any frontmatter field (not just description/body)
    ships to the host, so it must fail the no-secret-leak gate."""
    raw = (
        "---\nname: s\ndescription: clean\n"
        "metadata:\n  note: AWS_SECRET_ACCESS_KEY=" + "placeholder_secret_val_123\n"
        "---\nclean body\n"
    )
    report = eval_lite(raw)
    assert not report.passed
    assert any(c.name == "no_secret_leak" and not c.passed for c in report.checks)


def test_keyword_named_frontmatter_field_secret_fails_gate():
    """v0.11.1 #4: a `keyword: value` secret in a custom frontmatter field must
    fail the leak gate — JSON-serializing split the keyword from the value with a
    quote and let it through."""
    raw = "---\nname: s\ndescription: clean\ntoken: abcdef1234567890secretvalue\n---\nbody\n"
    report = eval_lite(raw)
    assert not report.passed
    assert any(c.name == "no_secret_leak" and not c.passed for c in report.checks)


def test_over_token_budget_fails_gate():
    huge = "word " * 6000  # well over the agentskills <5000-token body limit
    report = eval_lite(_md(huge))
    assert not report.passed
    assert any(c.name == "token_budget" and not c.passed for c in report.checks)


def test_eval_error_carries_report():
    report = eval_lite(_md("KEY=sk-DEADBEEF0123456789abcdefghij"))
    err = EvalError(report)
    assert err.report is report
    assert "no_secret_leak" in str(err)

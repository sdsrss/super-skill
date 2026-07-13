from super_skill.redact import redact_payload, redact_text

# Secret-shaped test inputs are assembled from fragments so repository secret
# scanners (e.g. GitHub push protection) don't flag these intentional fixtures
# as real leaks. At runtime they are the full shapes the redaction rules match.
_AWS_ID = "AKIA" + "ABCDEFGHIJKLMNOP"
_GHP = "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_SLACK = "xoxb-" + "123456789012-abcdefghijklmnop"
_SLACK2 = "xoxb-" + "1234567890-abcdefghij"
_STRIPE_LIVE = "sk_live_" + "abcdefghijklmnop1234567890"
_STRIPE_TEST = "sk_test_" + "abcdefghijklmnop1234567890"


def test_openai_key_redacted():
    s = "use sk-abcdefghij0123456789ABCDEFGHIJ as the key"
    red, counts = redact_text(s)
    assert "sk-abcdefghij0123456789" not in red
    assert "[REDACTED:openai_key]" in red
    assert counts.get("openai_key") == 1


def test_anthropic_key_redacted():
    s = "sk-ant-api03-AbCdEf1234567890xyz"
    red, counts = redact_text(s)
    assert "AbCdEf1234567890" not in red
    assert counts.get("anthropic_key") == 1


def test_github_and_aws_tokens():
    red, counts = redact_text(f"{_GHP} {_AWS_ID}")
    assert _GHP not in red
    assert _AWS_ID not in red
    assert "github_token" in counts and "aws_key" in counts


_JWT = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJ0ZXN0In0" + "." + "fakeSig0123456789"


def test_jwt_redacted():
    """P2-3 / audit P2-4: a bare JWT (no Bearer prefix) was unmatched — the three
    dot-joined base64url segments must redact."""
    red, counts = redact_text(f"session token is {_JWT} now")
    assert "eyJhbGci" not in red
    assert counts.get("jwt") == 1


def test_url_basic_auth_redacted():
    """P2-3 / audit P2-4: credentials embedded in a URL (user:pass@host) must
    redact while the host is preserved."""
    pw = "s3cr3t" + "passw0rd"
    red, counts = redact_text(f"clone https://alice:{pw}@github.com/x.git")
    assert pw not in red
    assert counts.get("basic_auth") == 1
    assert "github.com" in red  # host preserved, only creds dropped


def test_large_string_leaf_truncated():
    """P2-7 / audit P2-8: a huge string leaf (e.g. a 10MB tool output) is truncated
    so the WAL line stays bounded and the redaction regexes don't run over
    megabytes on the hook hot path."""
    big = "x" * (300 * 1024)
    red, marks = redact_payload({"stdout": big})
    assert len(red["stdout"]) < len(big)
    assert any(m.kind == "truncated" for m in marks)


def test_truncation_runs_after_redaction():
    """A secret in an over-long leaf is still redacted — redact runs before the
    length cut, so truncation can't split a secret mid-token."""
    payload = {"log": "sk-ant-" + "A" * 30 + (" filler" * 100000)}
    red, marks = redact_payload(payload)
    assert "sk-ant-AAAA" not in red["log"]
    assert any(m.kind == "anthropic_key" for m in marks)


def test_assigned_secret_keeps_key_drops_value():
    red, counts = redact_text('password="hunter2secret"')
    assert "hunter2secret" not in red
    assert "password" in red  # key name preserved for context
    assert counts.get("assigned_secret") == 1


def test_slack_token_redacted():
    """P4-2: slack_token rule was defined but never exercised — it feeds the
    zero-secret-leak hard gate, so silent breakage would leak a Slack token."""
    red, counts = redact_text(f"webhook uses {_SLACK} here")
    assert _SLACK not in red
    assert counts.get("slack_token") == 1


def test_private_key_block():
    block = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    red, counts = redact_text(block)
    assert "MIIabc" not in red
    assert counts.get("private_key") == 1


def test_email_and_home_path():
    red, counts = redact_text("me@example.com working in /home/alice/project")
    assert "me@example.com" not in red
    assert "/home/alice" not in red
    assert red.count("~") >= 1
    assert "email" in counts and "home_path" in counts


def test_underscore_env_var_secrets_redacted():
    """P0-1 / H1: underscore-delimited env-var secrets must not leak. The keyword
    is preceded by ``_`` (a word char), so a ``\\b`` left-anchor missed them."""
    for s, val in [
        ("DB_PASSWORD=SuperSecret123", "SuperSecret123"),
        ("MYSQL_PWD=hunter2xyz", "hunter2xyz"),
        ("AWS_SECRET_ACCESS_KEY=" + "placeholder_secret_val_123", "placeholder_secret_val_123"),
        ("SECRET_KEY=django-insecure-abc123", "django-insecure-abc123"),
        ("export API_KEY=plainvalue123", "plainvalue123"),  # space case must still work
    ]:
        red, counts = redact_text(s)
        assert val not in red, f"leaked value in {s!r} -> {red!r}"
        assert counts.get("assigned_secret") == 1
    # the bare word "password" in prose must NOT trip the rule
    red, counts = redact_text("update your password in the settings page")
    assert counts == {}


def test_assigned_secret_no_catastrophic_backtracking():
    """v0.11.1 #1: the broadened assigned_secret rule must not ReDoS on
    underscore-heavy input (it runs on every captured event before disk)."""
    import time

    payload = "api_key_" * 800  # 6.4KB snake_case blob — ~21s on the ReDoS version
    start = time.perf_counter()
    redact_text(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 2000, f"assigned_secret backtracking: {elapsed_ms:.0f}ms on 6.4KB"


def test_openai_project_key_fully_redacted():
    """v0.11.1 #3: sk-proj-/sk-svcacct- key bodies contain _ and -, so the tail
    after the first such char must not survive."""
    red, _ = redact_text("key sk-proj-abcdefghijklmnopqrstuvwx_MoreTail-secret99 end")
    assert "MoreTail" not in red and "secret99" not in red


def test_modern_token_formats_redacted():
    """P0-2 / H2: current provider key formats must be matched."""
    cases = {
        "sk-proj-abcdefghijklmnopqrstuvwx1234": "openai_key",
        "sk-svcacct-abcdefghijklmnopqrstuvwx12": "openai_key",
        _STRIPE_LIVE: "stripe_key",
        _STRIPE_TEST: "stripe_key",
        "github_pat_11ABCDEFG0abcdefghijKLMNOPqrstuv": "github_pat",
        "AIzaSyD1abcdefghijklmnopqrstuvwxyz012345": "gcp_key",
    }
    for token, kind in cases.items():
        red, counts = redact_text(f"the key is {token} ok")
        assert token not in red, f"{kind} leaked: {red!r}"
        assert counts.get(kind) == 1, f"{kind} not counted for {token!r}: {counts}"
    # legacy formats must not regress
    for legacy in ["sk-ant-api03-AbCdEf1234567890xyz", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ01",
                   _AWS_ID, _SLACK2]:
        red, _ = redact_text(legacy)
        assert legacy not in red, f"legacy regressed: {legacy!r} -> {red!r}"


def test_clean_text_unchanged():
    s = "run pytest then bump the version"
    red, counts = redact_text(s)
    assert red == s
    assert counts == {}


def test_redact_payload_deeply_nested_no_recursionerror():
    """P2-6 / L18: a pathologically deep payload (beyond Python's recursion
    limit) must not raise RecursionError — the guard caps depth and drops the
    over-deep subtree rather than crashing or leaking it."""
    obj: dict = {}
    cur = obj
    for _ in range(5000):  # well past sys.getrecursionlimit()
        cur["k"] = {}
        cur = cur["k"]
    cur["k"] = "leak sk-DEADBEEF0123456789abcdefghij"
    red, _ = redact_payload(obj)  # must not raise
    assert isinstance(red, dict)
    assert "DEADBEEF0123456789" not in str(red)  # over-deep subtree dropped, not leaked


def test_redact_payload_nested_and_marks():
    payload = {
        "cmd": "curl -H 'Authorization: Bearer abcdef0123456789ghijkl'",
        "env": {"API_KEY": "sk-0123456789abcdefghijklmnop"},
        "notes": ["contact me@example.com", "clean line"],
    }
    red, marks = redact_payload(payload)
    flat = str(red)
    assert "abcdef0123456789ghijkl" not in flat
    assert "sk-0123456789abcdefghij" not in flat
    assert "me@example.com" not in flat
    kinds = {m.kind for m in marks}
    assert "bearer_token" in kinds
    assert "email" in kinds
    # location must be recorded, value must not be
    assert all("REDACTED" not in m.location for m in marks)
    assert any(m.location.startswith("env") for m in marks)

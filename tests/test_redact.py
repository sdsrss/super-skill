from super_skill.redact import redact_payload, redact_text


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
    red, counts = redact_text("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 AKIAABCDEFGHIJKLMNOP")
    assert "ghp_ABCDEFGHIJ" not in red
    assert "AKIAABCDEFGHIJKLMNOP" not in red
    assert "github_token" in counts and "aws_key" in counts


def test_assigned_secret_keeps_key_drops_value():
    red, counts = redact_text('password="hunter2secret"')
    assert "hunter2secret" not in red
    assert "password" in red  # key name preserved for context
    assert counts.get("assigned_secret") == 1


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


def test_clean_text_unchanged():
    s = "run pytest then bump the version"
    red, counts = redact_text(s)
    assert red == s
    assert counts == {}


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

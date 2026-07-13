from pkg.detect import contains_secret

# Assembled at runtime so no complete credential literal exists in the source
# (push-protection-safe; same runtime behaviour as a hardcoded fixture).
FIXTURE_KEY = "sspk_live_" + "abc123def456ghi78" + "9jkl012mno345pq"


def test_detects_full_key():
    assert contains_secret(f"token={FIXTURE_KEY}")


def test_ignores_plain_text():
    assert not contains_secret("no credentials here")

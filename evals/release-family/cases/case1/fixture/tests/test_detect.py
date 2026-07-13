from pkg.detect import contains_secret

FIXTURE_KEY = "sspk_live_abc123def456ghi789jkl012mno345pq"


def test_detects_full_key():
    assert contains_secret(f"token={FIXTURE_KEY}")


def test_ignores_plain_text():
    assert not contains_secret("no credentials here")

"""Tiny credential detector used by the release pipeline."""

import re

_PATTERN = re.compile(r"sspk_live_[A-Za-z0-9]{32}")


def contains_secret(text: str) -> bool:
    """True iff text contains a complete sspk live-key credential."""
    return bool(_PATTERN.search(text))

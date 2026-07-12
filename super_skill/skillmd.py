"""Parse and hash SKILL.md files (YAML frontmatter + markdown body)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import yaml

from .schemas import SkillFrontmatter

_FENCE = "---"


class SkillMdError(ValueError):
    """Malformed SKILL.md (missing/broken frontmatter)."""


@dataclass(frozen=True)
class ParsedSkillMd:
    frontmatter: SkillFrontmatter
    body: str
    raw: str


def normalize(text: str) -> str:
    """Strip BOM and CRLF so hashes ignore meaningless byte differences
    (docs/02 §4.2 normalized hash)."""
    return text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def parse(text: str) -> ParsedSkillMd:
    """Split a SKILL.md into validated frontmatter + body.

    Frontmatter is the first ``---``-fenced YAML block. Raises SkillMdError if
    absent or not a mapping — the seed importer skips such directories rather
    than registering an invalid skill.
    """
    norm = normalize(text)
    if not norm.startswith(_FENCE):
        raise SkillMdError("missing YAML frontmatter fence")
    end = norm.find(f"\n{_FENCE}", len(_FENCE))
    if end == -1:
        raise SkillMdError("unterminated frontmatter fence")
    fm_text = norm[len(_FENCE) : end]
    body = norm[end + len(_FENCE) + 1 :].lstrip("\n")
    try:
        data = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        raise SkillMdError(f"invalid frontmatter YAML: {e}") from e
    if not isinstance(data, dict):
        raise SkillMdError("frontmatter is not a mapping")
    try:
        fm = SkillFrontmatter.model_validate(data)
    except ValueError as e:
        raise SkillMdError(f"frontmatter failed validation: {e}") from e
    return ParsedSkillMd(frontmatter=fm, body=body, raw=norm)

import pytest

from super_skill.skillmd import SkillMdError, content_hash, parse

VALID = """---
name: dep-resolver
description: Diagnose dependency resolution failures.
license: MIT
---
# Body
steps here
"""


def test_parse_valid():
    p = parse(VALID)
    assert p.frontmatter.name == "dep-resolver"
    assert p.frontmatter.license == "MIT"
    assert p.body.startswith("# Body")


def test_missing_fence():
    with pytest.raises(SkillMdError, match="missing"):
        parse("no frontmatter here")


def test_unterminated_fence():
    with pytest.raises(SkillMdError, match="unterminated"):
        parse("---\nname: x\ndescription: y\n")


def test_non_mapping():
    with pytest.raises(SkillMdError, match="not a mapping"):
        parse("---\n- just\n- a\n- list\n---\nbody")


def test_bad_name_rejected():
    bad = VALID.replace("dep-resolver", "Bad_Name")
    with pytest.raises(SkillMdError, match="validation"):
        parse(bad)


def test_hash_ignores_crlf_and_bom():
    lf = "---\nname: a\ndescription: d\n---\nbody\n"
    crlf = "﻿" + lf.replace("\n", "\r\n")
    assert content_hash(lf) == content_hash(crlf)

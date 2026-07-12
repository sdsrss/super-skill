"""GATE-2 harness: fixture self-check + verdict logic (evals/test-fix-family)."""

import importlib.util
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[1] / "evals" / "test-fix-family"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HARNESS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


grader = _load("grader")
gate2 = _load("gate2_report")

CASES = ["case1", "case2", "case3"]


@pytest.mark.parametrize("case", CASES)
def test_broken_fails_and_fixed_passes(case):
    """The grader is only trustworthy if the shipped broken.py fails its hidden
    verifier and the reference fixed.py passes it."""
    cdir = _HARNESS / "cases" / case
    assert grader.grade_case(cdir, cdir / "broken.py") is False
    assert grader.grade_case(cdir, cdir / "fixed.py") is True


def _arm(*triples):
    return {f"case{i + 1}": list(t) for i, t in enumerate(triples)}


def test_tie_with_less_effort_passes():
    mined = _arm((True, True, True), (True, True, True))
    hand = _arm((True, True, True), (True, True, True))
    v = gate2.compute_verdict(mined, hand, mined_hours=0.5, handwritten_hours=2.0)
    assert v["verdict_pass"] is True
    assert v["a_quality_not_worse"] and v["b_no_critical_regression"] and v["c_investment"]


def test_tie_but_more_effort_fails_on_c():
    mined = _arm((True, True, True))
    hand = _arm((True, True, True))
    v = gate2.compute_verdict(mined, hand, mined_hours=3.0, handwritten_hours=2.0)
    assert v["verdict_pass"] is False
    assert v["c_investment"] is False


def test_critical_regression_fails_on_b():
    # handwritten 3/3, mined 0/3 on the same case -> (b) trips even if totals tie
    mined = _arm((False, False, False), (True, True, True))
    hand = _arm((True, True, True), (False, False, False))
    v = gate2.compute_verdict(mined, hand, mined_hours=0.1, handwritten_hours=9.0)
    assert v["b_no_critical_regression"] is False
    assert v["verdict_pass"] is False


def test_mined_more_passes_within_1_5x_passes():
    mined = _arm((True, True, True), (True, True, True))
    hand = _arm((True, True, True), (False, False, False))
    v = gate2.compute_verdict(mined, hand, mined_hours=3.0, handwritten_hours=2.0)
    assert v["mined_pass_total"] > v["handwritten_pass_total"]
    assert v["c_investment"] is True  # 3.0 <= 1.5*2.0
    assert v["verdict_pass"] is True


def test_mined_fewer_passes_fails_on_a():
    mined = _arm((False, False, False))
    hand = _arm((True, True, True))
    v = gate2.compute_verdict(mined, hand, mined_hours=0.1, handwritten_hours=9.0)
    assert v["a_quality_not_worse"] is False
    assert v["verdict_pass"] is False

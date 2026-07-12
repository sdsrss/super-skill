"""B′ pilot harness: fixture self-check + verdict logic (evals/release-family)."""

import importlib.util
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parents[1] / "evals" / "release-family"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HARNESS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


grader = _load("grader")
report = _load("report")

CASES = ["case1", "case2", "case3", "case4", "case5", "n1", "n2"]


@pytest.mark.parametrize("case", CASES)
def test_fixture_fails_and_reference_passes(case):
    """The grader is only trustworthy if the shipped fixture/ fails its hidden
    verifier (task not done) and the reference/ solution passes it."""
    cdir = _HARNESS / "cases" / case
    assert grader.grade_case(cdir, cdir / "fixture") is False
    assert grader.grade_case(cdir, cdir / "reference") is True


def _arm(*triples):
    return {f"case{i + 1}": list(t) for i, t in enumerate(triples)}


def _data(**overrides):
    base = {
        "arms": {
            "none": _arm((False, False, True), (False, False, False)),
            "hybrid": _arm((True, True, True), (True, True, True)),
            "handwritten": _arm((True, True, True), (True, False, True)),
        },
        "negative_controls": {"hybrid_mistriggers": 0},
        "gates": {"instruction_gate_pass": True, "evallite_pass": True, "secret_leak": False},
        "hours": {"hybrid_total": 1.0, "handwritten_total": 2.0},
        "provenance": {"mined": 6, "external": 3, "prior": 1},
    }
    base.update(overrides)
    return base


def test_all_criteria_met_passes():
    v = report.compute_verdict(_data())
    assert v["a_quality"] and v["b_no_regression"] and v["c_investment"] and v["d_provenance"]
    assert v["verdict_pass"] is True


def test_mistrigger_fails_b():
    v = report.compute_verdict(_data(negative_controls={"hybrid_mistriggers": 1}))
    assert v["b_no_regression"] is False
    assert v["verdict_pass"] is False


def test_gate_failure_fails_b():
    gates = {"instruction_gate_pass": True, "evallite_pass": False, "secret_leak": False}
    v = report.compute_verdict(_data(gates=gates))
    assert v["b_no_regression"] is False


def test_provenance_below_half_fails_d():
    v = report.compute_verdict(_data(provenance={"mined": 4, "external": 5, "prior": 1}))
    assert v["d_provenance"] is False
    assert v["d_mined_share"] == 0.4
    assert v["verdict_pass"] is False


def test_tie_with_more_hours_fails_c():
    data = _data(hours={"hybrid_total": 3.0, "handwritten_total": 2.0})
    data["arms"]["handwritten"] = data["arms"]["hybrid"]  # exact tie on quality
    v = report.compute_verdict(data)
    assert v["c_investment"] is False
    assert v["verdict_pass"] is False


def test_more_passes_within_comparable_hours_passes_c():
    v = report.compute_verdict(_data(hours={"hybrid_total": 2.9, "handwritten_total": 2.0}))
    assert v["hybrid_pass_total"] > v["handwritten_pass_total"]
    assert v["c_investment"] is True  # 2.9 <= 1.5 * 2.0
    assert v["verdict_pass"] is True


def test_hybrid_below_none_fails_a():
    arms = {
        "none": _arm((True, True, True)),
        "hybrid": _arm((True, False, False)),
        "handwritten": _arm((False, False, False)),
    }
    v = report.compute_verdict(_data(arms=arms))
    assert v["a_quality"] is False
    assert v["verdict_pass"] is False


def test_stable_flip_vs_handwritten_fails_a():
    # equal totals but hybrid 0/3 where handwritten is 3/3 -> stricter reading trips
    arms = {
        "none": _arm((False, False, False), (False, False, False)),
        "hybrid": _arm((False, False, False), (True, True, True)),
        "handwritten": _arm((True, True, True), (False, False, False)),
    }
    v = report.compute_verdict(_data(arms=arms))
    assert v["a_quality"] is False
    assert v["verdict_pass"] is False

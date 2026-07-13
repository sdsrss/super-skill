from stats import calc, summarize


def test_calc():
    s = calc([1.0, 2.0, 3.0])
    assert s["mean"] == 2.0 and s["span"] == 2.0


def test_summarize():
    assert summarize([1.0, 3.0]) == "mean=2.00 span=2.00"

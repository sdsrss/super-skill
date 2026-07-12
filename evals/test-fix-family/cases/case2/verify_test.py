from broken import classify


def test_classify():
    assert classify(60) == "pass"  # boundary is a pass
    assert classify(61) == "pass"
    assert classify(59) == "fail"
    assert classify(0) == "fail"

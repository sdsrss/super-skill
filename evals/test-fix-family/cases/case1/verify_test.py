from broken import last_n


def test_last_n():
    assert last_n([1, 2, 3, 4, 5], 2) == [4, 5]
    assert last_n([1, 2, 3], 3) == [1, 2, 3]
    assert last_n([1, 2, 3], 0) == []
    assert last_n([1, 2, 3], 1) == [3]

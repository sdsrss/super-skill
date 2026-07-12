from broken import running_max


def test_running_max():
    assert running_max([3, 1, 4, 1, 5]) == [3, 3, 4, 4, 5]
    assert running_max([-5, -2, -9]) == [-5, -2, -2]  # all-negative exposes the 0-init bug
    assert running_max([]) == []

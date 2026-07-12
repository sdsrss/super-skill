def last_n(items, n):
    """Return the last n items of a list, in order.

    last_n([1,2,3,4,5], 2) -> [4, 5]; last_n(x, 0) -> [].
    """
    return items[len(items) - n:] if n > 0 else []

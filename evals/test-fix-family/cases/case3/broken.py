def running_max(nums):
    """Return a list where element i is the max of nums[0..i].

    running_max([3,1,4,1,5]) -> [3,3,4,4,5]; running_max([]) -> [].
    """
    out = []
    m = 0
    for n in nums:
        m = max(m, n)
        out.append(m)
    return out

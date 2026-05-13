"""BF-001: Off-by-one error in range-based summation.

Bug type: off-by-one error (uses range(start, end) instead of range(start, end+1))
"""


def sum_range(start: int, end: int) -> int:
    """Return the sum of all integers from start to end inclusive.

    Examples:
        >>> sum_range(1, 5)
        15
        >>> sum_range(10, 10)
        10
        >>> sum_range(0, 0)
        0
    """
    total = 0
    for i in range(start, end):  # BUG: misses the end value
        total += i
    return total


# CORRECTED:
# for i in range(start, end + 1):

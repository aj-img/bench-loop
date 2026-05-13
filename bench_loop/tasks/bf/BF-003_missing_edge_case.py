"""BF-003: Missing edge case for empty list.

Bug type: missing edge case (empty list)
"""


def find_max(values: list[int]) -> int:
    """Return the maximum value in a non-empty list of integers.

    Examples:
        >>> find_max([3, 1, 4, 1, 5])
        5
        >>> find_max([-1, -2, -3])
        -1
    """
    max_val = values[0]
    for i in range(1, len(values)):  # BUG: crashes on empty list — no guard
        if values[i] > max_val:
            max_val = values[i]
    return max_val


# CORRECTED:
# if not values:
#     raise ValueError("Cannot find max of empty list")
# max_val = values[0]

"""BF-009: Infinite loop potential — index never advances.

Bug type: infinite loop potential
"""


def find_first_positive(numbers: list[int]) -> int | None:
    """Return the index of the first positive number, or None.

    Examples:
        >>> find_first_positive([-1, -2, 3, 4])
        2
        >>> find_first_positive([-1, -2, -3])
        None
        >>> find_first_positive([1, 2, 3])
        0
    """
    idx = 0
    while numbers[idx] <= 0:  # BUG: idx never increments → infinite loop if no positive
        idx += 1  # This is after the check, but if no positive exists, list index error or infinite loop
    return idx


# CORRECTED:
# for idx, num in enumerate(numbers):
#     if num > 0:
#         return idx
# return None

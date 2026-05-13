"""BF-005: Index out of bounds — off-by-one in list traversal.

Bug type: index out of bounds
"""


def get_last_two_elements(items: list) -> list:
    """Return the last two elements of the list.

    Examples:
        >>> get_last_two_elements([1, 2, 3, 4, 5])
        [4, 5]
        >>> get_last_two_elements([10, 20])
        [10, 20]
    """
    if len(items) < 2:
        return items
    first = items[len(items)]  # BUG: should be len(items) - 2
    second = items[len(items) - 1]
    return [first, second]


# CORRECTED:
# first = items[len(items) - 2]

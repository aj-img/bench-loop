"""BF-010: Incorrect sort order — sorts ascending when descending is needed.

Bug type: incorrect sort order
"""


def top_k_largest(values: list[int], k: int) -> list[int]:
    """Return the k largest values in descending order.

    Examples:
        >>> top_k_largest([5, 1, 3, 8, 2], 3)
        [8, 5, 3]
        >>> top_k_largest([10, 20], 1)
        [20]
    """
    sorted_vals = sorted(values, reverse=False)  # BUG: reverse=False gives ascending
    return sorted_vals[:k]


# CORRECTED:
# sorted_vals = sorted(values, reverse=True)

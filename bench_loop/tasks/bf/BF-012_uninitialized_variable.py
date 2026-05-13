"""BF-012: Uninitialized variable — referenced before assignment.

Bug type: uninitialized variable
"""


def compute_average(numbers: list[float]) -> float:
    """Return the average of a list of numbers.

    Examples:
        >>> compute_average([1, 2, 3, 4, 5])
        3.0
        >>> compute_average([10, 20])
        15.0
    """
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)  # BUG: if numbers is empty, len is 0 → ZeroDivisionError


# CORRECTED:
# if not numbers:
#     return 0.0
# return total / len(numbers)

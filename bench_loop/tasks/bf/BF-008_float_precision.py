"""BF-008: Float precision error in financial calculation.

Bug type: float precision error
"""


def calculate_change(amount_tendered: float, total_cost: float) -> float:
    """Return change due, rounded to 2 decimal places.

    Examples:
        >>> calculate_change(10.0, 3.70)
        6.3
        >>> calculate_change(5.0, 1.99)
        3.01
    """
    change = amount_tendered - total_cost
    return change  # BUG: floating-point imprecision; should round to 2 decimals


# CORRECTED:
# return round(change, 2)

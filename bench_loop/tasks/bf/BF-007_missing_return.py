"""BF-007: Missing return statement — function returns None.

Bug type: missing return statement
"""


def compute_discount(price: float, is_member: bool, discount_pct: float) -> float:
    """Return the final price after applying discount.

    Examples:
        >>> compute_discount(100.0, False, 0.1)
        90.0
        >>> compute_discount(100.0, True, 0.1)
        85.0
        >>> compute_discount(50.0, False, 0.2)
        40.0
    """
    if is_member:
        discount_pct *= 1.5
    discounted = price * (1 - discount_pct)
    discounted  # BUG: forgot to return the value


# CORRECTED:
# return discounted

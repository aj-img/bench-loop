"""BF-004: Type confusion — compares string to integer.

Bug type: type confusion (str vs int)
"""


def calculate_total_price(base_price: str, tax_rate: float, quantity: int) -> float:
    """Return total price = base_price * (1 + tax_rate) * quantity.

    Examples:
        >>> calculate_total_price("100.00", 0.1, 2)
        220.0
        >>> calculate_total_price("50", 0.05, 1)
        52.5
    """
    price = base_price  # BUG: base_price is a str, not converted to float
    return price * (1 + tax_rate) * quantity


# CORRECTED:
# price = float(base_price)

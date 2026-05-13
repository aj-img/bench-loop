"""BF-002: Logic inversion — checks != instead of ==.

Bug type: logic inversion (!= vs ==)
"""


def is_palindrome(text: str) -> bool:
    """Return True if text reads the same forwards and backwards.

    Examples:
        >>> is_palindrome("racecar")
        True
        >>> is_palindrome("hello")
        False
        >>> is_palindrome("a")
        True
    """
    cleaned = text.lower().replace(" ", "")
    return cleaned != cleaned[::-1]  # BUG: inverted comparison


# CORRECTED:
# return cleaned == cleaned[::-1]

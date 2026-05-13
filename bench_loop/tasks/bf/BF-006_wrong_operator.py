"""BF-006: Wrong comparison operator — < instead of <=.

Bug type: wrong operator (< vs <=)
"""


def classify_score(score: float) -> str:
    """Return the grade classification for a numeric score (0-100).

    Examples:
        >>> classify_score(90)
        'A'
        >>> classify_score(79)
        'B'
        >>> classify_score(69)
        'C'
        >>> classify_score(59)
        'D'
        >>> classify_score(50)
        'F'
        >>> classify_score(100)
        'A'
    """
    if score < 90:  # BUG: should be <= for exactly 90 → A
        if score < 80:
            if score < 70:
                if score < 60:
                    return "D"
                return "C"
            return "B"
        return "A"
    return "F"


# CORRECTED:
# if score <= 90:
# followed by elif chain, or better yet:
# if score >= 90:
#     return "A"
# elif score >= 80:
#     return "B"
# elif score >= 70:
#     return "C"
# elif score >= 60:
#     return "D"
# return "F"

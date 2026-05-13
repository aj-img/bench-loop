"""BF-011: Regex boundary error — matches partial words.

Bug type: regex boundary error
"""


def extract_domain(url: str) -> str:
    """Extract the domain from a URL string.

    Examples:
        >>> extract_domain("https://example.com/page")
        'example.com'
        >>> extract_domain("http://test.org")
        'test.org'
    """
    import re
    match = re.search(r'[A-Za-z0-9.-]+\.[A-Za-z]{2,}', url)  # BUG: no word boundary, may match partial
    return match.group(0) if match else ""


# CORRECTED:
# match = re.search(r'(?:https?://)?(?:www\.)?([A-Za-z0-9.-]+\.[A-Za-z]{2,})', url)
# return match.group(1) if match else ""

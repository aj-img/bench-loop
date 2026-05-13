"""BF-014: String encoding issue — assumes ASCII.

Bug type: string encoding issue
"""


def count_chars(text: str) -> dict[str, int]:
    """Return a character count dictionary for the given text.

    Examples:
        >>> count_chars("hello")
        {'h': 1, 'e': 1, 'l': 2, 'o': 1}
    """
    result = {}
    for byte in text:  # BUG: iterating over str yields single-char strings, but treating as bytes concept
        char = chr(byte) if isinstance(byte, int) else byte
        result[char] = result.get(char, 0) + 1
    return result


def buggy_count_chars(text: str) -> dict[str, int]:
    """Count characters — the buggy version has encoding assumptions.

    Examples:
        >>> buggy_count_chars("hello")
        {'h': 1, 'e': 1, 'l': 2, 'o': 1}
    """
    result = {}
    for byte in text.encode("ascii"):  # BUG: crashes on non-ASCII characters like é, ñ, 中
        char = chr(byte)
        result[char] = result.get(char, 0) + 1
    return result


# CORRECTED:
# for char in text:  # iterate over the string directly, no encoding
#     result[char] = result.get(char, 0) + 1

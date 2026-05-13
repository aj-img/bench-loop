"""BF-013: Wrong mutable default argument.

Bug type: wrong default argument
"""


def append_item(item: str, target_list: list | None = None) -> list:
    """Append an item to a list and return it.

    Examples:
        >>> append_item("a")
        ['a']
        >>> append_item("b")
        ['b']
    """
    if target_list is None:
        target_list = []  # This is correct
    target_list.append(item)
    return target_list


def safe_append_default(item: str, target_list: list = []) -> list:
    """Append an item to a list and return it (with buggy default).

    Examples:
        >>> safe_append_default("a")
        ['a']
        >>> safe_append_default("b")
        ['b']
        >>> safe_append_default("c")
        ['c']
    """
    target_list.append(item)
    return target_list


# CORRECTED:
# def safe_append_default(item: str, target_list: list | None = None) -> list:
#     if target_list is None:
#         target_list = []
#     target_list.append(item)
#     return target_list

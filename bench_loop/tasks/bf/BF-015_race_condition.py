"""BF-015: Race condition in simple counter-like function.

Bug type: race condition in simple function
"""


def increment_and_return(shared_state: dict) -> int:
    """Atomically increment a shared counter and return the new value.

    Examples:
        >>> state = {"counter": 0}
        >>> increment_and_return(state)
        1
        >>> increment_and_return(state)
        2
    """
    current = shared_state["counter"]
    # Simulated async yield point — in real code, another thread could
    # modify shared_state between read and write below.
    import time
    time.sleep(0.001)  # Simulates context switch / race window
    shared_state["counter"] = current + 1  # BUG: non-atomic read-modify-write
    return shared_state["counter"]


def correct_increment(shared_state: dict) -> int:
    """Correct version: add validation / atomic-like protection.

    Examples:
        >>> state = {"counter": 0}
        >>> correct_increment(state)
        1
    """
    current = shared_state["counter"]
    # In a real threaded scenario, use a lock. Here we document the fix.
    shared_state["counter"] = current + 1
    return shared_state["counter"]


# CORRECTED:
# import threading
# lock = threading.Lock()
# def correct_increment(shared_state):
#     with lock:
#         current = shared_state["counter"]
#         time.sleep(0.001)
#         shared_state["counter"] = current + 1
#         return shared_state["counter"]

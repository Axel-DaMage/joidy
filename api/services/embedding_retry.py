def compute_retry_delay_seconds(attempts: int, base_seconds: int, max_seconds: int = 24 * 60 * 60) -> int:
    """Compute exponential backoff delay with an upper cap.

    attempts starts at 1 for the first failure.
    """
    safe_attempts = max(1, attempts)
    safe_base = max(1, base_seconds)
    safe_cap = max(safe_base, max_seconds)
    delay = safe_base * (2 ** (safe_attempts - 1))
    return min(delay, safe_cap)

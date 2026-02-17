"""
In-memory per-IP rate limiter for transcription endpoints.
No external dependencies — uses a dict of timestamps.
"""

import time
import threading
from fastapi import Request, HTTPException


# Config
RATE_LIMIT = 10  # max requests per window
RATE_WINDOW = 60  # window in seconds

# Storage: { ip: [timestamp, ...] }
_requests: dict[str, list[float]] = {}
_lock = threading.Lock()

# Clean up stale entries every N calls to avoid unbounded growth
_CLEANUP_INTERVAL = 100
_call_count = 0


def _cleanup(now: float) -> None:
    """Remove entries older than the rate window."""
    cutoff = now - RATE_WINDOW
    stale_keys = [ip for ip, ts_list in _requests.items() if not ts_list or ts_list[-1] < cutoff]
    for key in stale_keys:
        del _requests[key]


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces per-IP rate limiting.

    Raises HTTPException 429 if the client exceeds RATE_LIMIT requests
    within the RATE_WINDOW.
    """
    global _call_count

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    with _lock:
        _call_count += 1
        if _call_count % _CLEANUP_INTERVAL == 0:
            _cleanup(now)

        timestamps = _requests.get(client_ip)
        if timestamps is None:
            _requests[client_ip] = [now]
            return

        # Trim timestamps outside the current window
        cutoff = now - RATE_WINDOW
        while timestamps and timestamps[0] <= cutoff:
            timestamps.pop(0)

        if len(timestamps) >= RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per {RATE_WINDOW} seconds.",
            )

        timestamps.append(now)

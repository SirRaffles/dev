"""
In-memory per-IP rate limiter for transcription endpoints.
No external dependencies — uses a dict of timestamps.
"""

import time
import threading
from fastapi import Request, HTTPException


# Config — 10/min was far too tight: the UI polls /health and /jobs
# continuously, so a handful of filter clicks were enough to 429. With the
# IP allowlist already restricting traffic to loopback + Tailscale + RFC1918,
# 120/min is plenty of headroom for a single user while still throttling
# abuse from a compromised LAN device.
RATE_LIMIT = 120  # max requests per window
RATE_WINDOW = 60  # window in seconds
_MAX_TRACKED_IPS = 10_000  # cap to prevent unbounded memory growth

# Storage: { ip: [timestamp, ...] }
_requests: dict[str, list[float]] = {}
_lock = threading.Lock()

# Clean up stale entries every N calls to avoid unbounded growth
_CLEANUP_INTERVAL = 100
_call_count = 0


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting proxy headers when present."""
    # Check X-Forwarded-For (set by nginx/reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # First IP in the chain is the original client
        return forwarded_for.split(",")[0].strip()
    # Check X-Real-IP (set by some proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


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

    client_ip = _get_client_ip(request)
    now = time.monotonic()

    with _lock:
        _call_count += 1
        if _call_count % _CLEANUP_INTERVAL == 0:
            _cleanup(now)

        # Evict oldest entries if we exceed the IP tracking cap
        if len(_requests) >= _MAX_TRACKED_IPS and client_ip not in _requests:
            _cleanup(now)
            # If still at cap after cleanup, evict the oldest entry
            if len(_requests) >= _MAX_TRACKED_IPS:
                oldest_key = next(iter(_requests))
                del _requests[oldest_key]

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

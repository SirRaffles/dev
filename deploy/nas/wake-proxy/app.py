"""
Wake-on-LAN Proxy for Whisper Transcription App.

Sits between the NAS frontend and the Mac backend.
Auto-wakes the Mac via WoL when a request arrives and the Mac is sleeping.
Transparently proxies all requests to the Mac backend when awake.
"""

import asyncio
import logging
import os
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from wakeonlan import send_magic_packet

# Configuration
MAC_BACKEND_URL = os.environ.get("MAC_BACKEND_URL", "http://100.102.54.116:8000")
MAC_MAC_ADDRESS = os.environ.get("MAC_MAC_ADDRESS", "16:60:3e:7b:01:32")
MAC_API_KEY = os.environ.get("MAC_API_KEY", "")
HEALTH_CHECK_INTERVAL = 15  # seconds
WAKE_TIMEOUT = 180  # 3 minutes max wait for wake
CONSECUTIVE_FAILURES_TO_SLEEP = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wake-proxy")

app = FastAPI(title="Whisper Wake Proxy")


class MacState:
    """Tracks the Mac's current state."""

    def __init__(self):
        self.state = "sleeping"  # awake, sleeping, waking
        self.model_loaded = False
        self.last_seen_awake = None
        self.wake_started_at = None
        self.consecutive_failures = 0

    @property
    def estimated_ready_in(self):
        if self.state != "waking" or not self.wake_started_at:
            return None
        elapsed = time.time() - self.wake_started_at
        remaining = max(0, 90 - elapsed)
        return round(remaining)


mac_state = MacState()


async def check_backend_health():
    """Ping the Mac backend and update state."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{MAC_BACKEND_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                mac_state.consecutive_failures = 0
                mac_state.model_loaded = data.get("model_loaded", False)
                mac_state.last_seen_awake = time.time()

                if mac_state.state in ("sleeping", "waking"):
                    old_state = mac_state.state
                    mac_state.state = "awake"
                    logger.info("Mac is now awake (was %s), model_loaded=%s", old_state, mac_state.model_loaded)
                return True
    except Exception:
        mac_state.consecutive_failures += 1

        if mac_state.state == "awake" and mac_state.consecutive_failures >= CONSECUTIVE_FAILURES_TO_SLEEP:
            mac_state.state = "sleeping"
            mac_state.model_loaded = False
            logger.info("Mac transitioned to sleeping after %d failures", mac_state.consecutive_failures)

        # Timeout waking state after WAKE_TIMEOUT
        if mac_state.state == "waking" and mac_state.wake_started_at:
            if time.time() - mac_state.wake_started_at > WAKE_TIMEOUT:
                mac_state.state = "sleeping"
                mac_state.wake_started_at = None
                logger.warning("Wake timed out after %ds, back to sleeping", WAKE_TIMEOUT)

    return False


async def health_check_loop():
    """Background task: periodically check Mac health and send WoL while waking."""
    while True:
        await check_backend_health()

        # Send redundant WoL packets while waking
        if mac_state.state == "waking":
            try:
                send_magic_packet(MAC_MAC_ADDRESS)
                logger.debug("Sent redundant WoL packet to %s", MAC_MAC_ADDRESS)
            except Exception as e:
                logger.warning("Failed to send WoL packet: %s", e)

        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


@app.on_event("startup")
async def startup():
    # Do an initial health check
    await check_backend_health()
    logger.info("Initial Mac state: %s (backend_url=%s, mac=%s)", mac_state.state, MAC_BACKEND_URL, MAC_MAC_ADDRESS)
    # Start background health checker
    asyncio.create_task(health_check_loop())


@app.get("/api/wake-status")
async def wake_status():
    return {
        "mac_state": mac_state.state,
        "model_loaded": mac_state.model_loaded,
        "backend_healthy": mac_state.state == "awake",
        "last_seen_awake": mac_state.last_seen_awake,
        "wake_started_at": mac_state.wake_started_at,
        "estimated_ready_in": mac_state.estimated_ready_in,
    }


def trigger_wake():
    """Send WoL and transition to waking state."""
    if mac_state.state == "waking":
        return  # Already waking

    mac_state.state = "waking"
    mac_state.wake_started_at = time.time()
    mac_state.consecutive_failures = 0

    try:
        send_magic_packet(MAC_MAC_ADDRESS)
        logger.info("Sent WoL magic packet to %s", MAC_MAC_ADDRESS)
    except Exception as e:
        logger.error("Failed to send WoL packet: %s", e)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_backend(request: Request, path: str):
    # If Mac is sleeping, trigger wake and return 503
    if mac_state.state == "sleeping":
        trigger_wake()
        return JSONResponse(
            status_code=503,
            content={
                "status": "waking",
                "message": "Mac is sleeping. Wake-on-LAN sent, waiting for startup.",
                "retry_after": 90,
                "estimated_ready_in": mac_state.estimated_ready_in,
            },
            headers={"Retry-After": "90"},
        )

    # If Mac is waking, return 503 with progress
    if mac_state.state == "waking":
        return JSONResponse(
            status_code=503,
            content={
                "status": "waking",
                "message": "Mac is waking up and loading models...",
                "estimated_ready_in": mac_state.estimated_ready_in,
            },
            headers={"Retry-After": str(max(5, mac_state.estimated_ready_in or 30))},
        )

    # Mac is awake -- proxy the request
    target_url = f"{MAC_BACKEND_URL}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    # Read the request body
    body = await request.body()

    # Forward headers, removing hop-by-hop headers
    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in ("host", "transfer-encoding", "connection", "authorization"):
            headers[key] = value
    # Inject backend API key (NAS auth is handled by nginx Basic Auth)
    if MAC_API_KEY:
        headers["X-API-Key"] = MAC_API_KEY

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
            )

        # Forward response headers, filtering hop-by-hop
        response_headers = {}
        for key, value in resp.headers.items():
            if key.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                response_headers[key] = value

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"detail": "Backend request timed out"})
    except httpx.ConnectError:
        # Backend went down mid-request -- mark as sleeping
        mac_state.state = "sleeping"
        mac_state.model_loaded = False
        return JSONResponse(status_code=503, content={"detail": "Backend became unreachable"})

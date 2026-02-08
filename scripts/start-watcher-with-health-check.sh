#!/bin/bash
#
# Start the Just Press Record Auto-Transcription Watcher
# with backend health check and wait.
#
# This script waits for the backend to be available before starting
# the watcher, preventing early failures when used with launchd.
#
# Usage: ./scripts/start-watcher-with-health-check.sh [--scan-existing] [--debug]
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WATCHER_DIR="$PROJECT_DIR/watcher"

# Backend configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
BACKEND_HEALTH_ENDPOINT="$BACKEND_URL/health"

# Timing configuration
MAX_WAIT_SECONDS=300  # Maximum time to wait for backend (5 minutes)
CHECK_INTERVAL=10     # Seconds between health checks
STARTUP_DELAY=30      # Initial delay before first check (let system settle)

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if backend is healthy
check_backend_health() {
    response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$BACKEND_HEALTH_ENDPOINT" 2>/dev/null)
    if [ "$response" = "200" ]; then
        # Verify model is loaded
        health_data=$(curl -s --connect-timeout 5 "$BACKEND_HEALTH_ENDPOINT" 2>/dev/null)
        if echo "$health_data" | grep -q '"model_loaded": true\|"model_loaded":true'; then
            return 0
        fi
    fi
    return 1
}

# Wait for backend to be available
wait_for_backend() {
    log "Waiting for backend at $BACKEND_HEALTH_ENDPOINT..."

    # Initial delay to let system settle on boot
    log "Initial startup delay: ${STARTUP_DELAY}s"
    sleep "$STARTUP_DELAY"

    elapsed=0
    while [ $elapsed -lt $MAX_WAIT_SECONDS ]; do
        if check_backend_health; then
            log "Backend is healthy and ready!"
            return 0
        fi

        log "Backend not ready yet (waited ${elapsed}s of ${MAX_WAIT_SECONDS}s). Checking again in ${CHECK_INTERVAL}s..."
        sleep "$CHECK_INTERVAL"
        elapsed=$((elapsed + CHECK_INTERVAL))
    done

    log "WARNING: Backend not available after ${MAX_WAIT_SECONDS}s, starting watcher anyway"
    log "The watcher will handle backend unavailability with retries"
    return 1
}

# Load HF_TOKEN from .env if available
if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
    export HF_TOKEN
fi

# Check if venv exists
if [ ! -d "$WATCHER_DIR/.venv" ]; then
    log "ERROR: Virtual environment not found at $WATCHER_DIR/.venv"
    log "Please run the installer first: ./scripts/install-watcher.sh"
    exit 1
fi

# Wait for backend to be available
wait_for_backend

log "Starting JPR Watcher..."

# Run the watcher
cd "$WATCHER_DIR"
exec .venv/bin/python jpr_watcher.py "$@"

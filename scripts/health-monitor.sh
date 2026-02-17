#!/bin/bash
#
# Health monitor for Davrine Transcription App services.
# Checks backend, frontend, and NAS proxy. Sends macOS notifications on failure.
#
# Usage: Run via launchd (com.whisper.health-monitor) every 5 minutes.
#

BACKEND_URL="http://localhost:8000/health"
FRONTEND_URL="http://localhost:3000"
NAS_PROXY_URL="http://192.168.50.171:8150"
STATE_FILE="$HOME/.whisper_health_state"

notify() {
    osascript -e "display notification \"$2\" with title \"$1\" sound name \"Basso\"" 2>/dev/null
}

check_service() {
    local url="$1"
    local timeout="${2:-5}"
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$timeout" --max-time "$timeout" "$url" 2>/dev/null)
    if [ "$status" -ge 200 ] 2>/dev/null && [ "$status" -lt 500 ] 2>/dev/null; then
        echo "up"
    else
        echo "down"
    fi
}

get_prev() {
    local key="$1"
    if [ -f "$STATE_FILE" ]; then
        grep "^${key}=" "$STATE_FILE" 2>/dev/null | cut -d= -f2
    fi
}

# Check services
backend=$(check_service "$BACKEND_URL")
frontend=$(check_service "$FRONTEND_URL")
nas=$(check_service "$NAS_PROXY_URL" 3)

# Notify on state transitions
prev_backend=$(get_prev backend)
prev_frontend=$(get_prev frontend)
prev_nas=$(get_prev nas)

[ "$backend" = "down" ] && [ "$prev_backend" != "down" ] && notify "Whisper Monitor" "Backend is DOWN (port 8000)"
[ "$backend" = "up" ] && [ "$prev_backend" = "down" ] && notify "Whisper Monitor" "Backend is back UP"

[ "$frontend" = "down" ] && [ "$prev_frontend" != "down" ] && notify "Whisper Monitor" "Frontend is DOWN (port 3000)"
[ "$frontend" = "up" ] && [ "$prev_frontend" = "down" ] && notify "Whisper Monitor" "Frontend is back UP"

[ "$nas" = "down" ] && [ "$prev_nas" != "down" ] && notify "Whisper Monitor" "NAS proxy is DOWN (8150)"
[ "$nas" = "up" ] && [ "$prev_nas" = "down" ] && notify "Whisper Monitor" "NAS proxy is back UP"

# Save state
printf "backend=%s\nfrontend=%s\nnas=%s\n" "$backend" "$frontend" "$nas" > "$STATE_FILE"

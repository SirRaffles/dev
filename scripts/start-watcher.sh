#!/bin/bash
#
# Start the Just Press Record Auto-Transcription Watcher
#
# Usage: ./scripts/start-watcher.sh [--scan-existing] [--debug]
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WATCHER_DIR="$PROJECT_DIR/watcher"
PLIST_NAME="com.whisper.jpr-watcher.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running as launchd service
if launchctl list | grep -q "com.whisper.jpr-watcher"; then
    echo -e "${GREEN}Watcher is running as a launchd service${NC}"
    echo ""
    echo "To stop:  launchctl unload $LAUNCH_AGENTS_DIR/$PLIST_NAME"
    echo "To restart: launchctl unload $LAUNCH_AGENTS_DIR/$PLIST_NAME && launchctl load $LAUNCH_AGENTS_DIR/$PLIST_NAME"
    exit 0
fi

# Load HF_TOKEN from .env if available
if [ -z "$HF_TOKEN" ] && [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
    export HF_TOKEN
fi

# Check if venv exists
if [ ! -d "$WATCHER_DIR/.venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running installer...${NC}"
    "$SCRIPT_DIR/install-watcher.sh"
    exit $?
fi

echo -e "${BLUE}Starting JPR Watcher...${NC}"
echo ""

# Run the watcher directly (for manual/interactive use)
cd "$WATCHER_DIR"
exec .venv/bin/python jpr_watcher.py "$@"

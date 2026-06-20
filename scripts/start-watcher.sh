#!/bin/bash
#
# Start the Just Press Record Auto-Transcription Watcher
#
# Usage: ./scripts/start-watcher.sh [--scan-existing] [--debug]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WATCHER_DIR="$PROJECT_DIR/watcher"
PLIST_NAME="com.whisper.jpr-watcher.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
WHISPER_ENV="$HOME/.whisper-env"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running as launchd service during manual/interactive use.
# When launchd itself starts this script, the service is necessarily listed;
# exiting there prevents the watcher process from ever starting.
if [ -t 1 ] && launchctl list | grep -q "com.whisper.jpr-watcher"; then
    echo -e "${GREEN}Watcher is running as a launchd service${NC}"
    echo ""
    echo "To stop:  launchctl unload $LAUNCH_AGENTS_DIR/$PLIST_NAME"
    echo "To restart: launchctl unload $LAUNCH_AGENTS_DIR/$PLIST_NAME && launchctl load $LAUNCH_AGENTS_DIR/$PLIST_NAME"
    exit 0
fi

# Load secrets from ~/.whisper-env (required to be mode 0600).
if [ -f "$WHISPER_ENV" ]; then
    mode=$(stat -f %Lp "$WHISPER_ENV")
    if [ "$mode" != "600" ]; then
        echo -e "${RED}Error: $WHISPER_ENV has mode $mode; must be 600.${NC}" >&2
        echo -e "${YELLOW}Fix with: chmod 600 $WHISPER_ENV${NC}" >&2
        exit 1
    fi
    set -a
    # shellcheck disable=SC1090
    source "$WHISPER_ENV"
    set +a
fi

# Check if venv exists
if [ ! -d "$WATCHER_DIR/.venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running installer...${NC}"
    "$SCRIPT_DIR/install-watcher.sh"
    exit $?
fi

# Ensure log directory exists with restrictive permissions (audit #21)
umask 077
mkdir -p "$HOME/Library/Logs/whisper"

echo -e "${BLUE}Starting JPR Watcher...${NC}"
echo ""

# Run the watcher directly (for manual/interactive use)
cd "$WATCHER_DIR"
exec .venv/bin/python jpr_watcher.py "$@"

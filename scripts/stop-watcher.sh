#!/bin/bash
#
# Stop the Just Press Record Auto-Transcription Watcher
#
# Usage: ./scripts/stop-watcher.sh
#

PLIST_NAME="com.whisper.jpr-watcher.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if launchctl list | grep -q "com.whisper.jpr-watcher"; then
    echo "Stopping watcher service..."
    launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
    echo -e "${GREEN}Watcher service stopped${NC}"
else
    echo -e "${YELLOW}Watcher service is not running${NC}"
fi

# Also kill any manual instances
pkill -f "jpr_watcher.py" 2>/dev/null && echo "Stopped manual watcher process" || true

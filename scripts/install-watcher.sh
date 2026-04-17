#!/bin/bash
#
# Install the Just Press Record Auto-Transcription Watcher
#
# This script:
# 1. Creates a Python virtual environment for the watcher
# 2. Installs dependencies
# 3. Installs the launchd plist for auto-start on login
# 4. Starts the watcher service
#
# Usage: ./scripts/install-watcher.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WATCHER_DIR="$PROJECT_DIR/watcher"
PLIST_NAME="com.whisper.jpr-watcher.plist"
PLIST_SRC="$PROJECT_DIR/deploy/launchd/$PLIST_NAME"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  JPR Watcher Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Secrets live in ~/.whisper-env (mode 0600) and are sourced by the wrapper script.
if [ ! -f "$HOME/.whisper-env" ]; then
    echo -e "${YELLOW}Warning: ~/.whisper-env not found.${NC}"
    echo -e "${YELLOW}Create it with HF_TOKEN_WATCHER and set chmod 600 ~/.whisper-env${NC}"
    echo ""
fi

# Check for Python 3.11+
PYTHON_CMD=""
for py in python3.11 python3.12 python3; do
    if command -v $py &> /dev/null; then
        version=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_CMD=$py
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.11+ is required${NC}"
    echo -e "${YELLOW}Install with: brew install python@3.11${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python: $PYTHON_CMD${NC}"

# Check if iCloud folder exists
ICLOUD_PATH="$HOME/Library/Mobile Documents/iCloud~com~openplanetsoftware~just-press-record/Documents"
if [ ! -d "$ICLOUD_PATH" ]; then
    echo -e "${YELLOW}Warning: Just Press Record iCloud folder not found${NC}"
    echo -e "${YELLOW}Expected: $ICLOUD_PATH${NC}"
    echo -e "${YELLOW}Make sure Just Press Record is installed and iCloud is enabled${NC}"
    echo ""
fi

# Create virtual environment
echo -e "${BLUE}Creating Python virtual environment...${NC}"
if [ -d "$WATCHER_DIR/.venv" ]; then
    echo "  Virtual environment already exists"
else
    $PYTHON_CMD -m venv "$WATCHER_DIR/.venv"
    echo "  Created: $WATCHER_DIR/.venv"
fi

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
"$WATCHER_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$WATCHER_DIR/.venv/bin/pip" install --quiet -r "$WATCHER_DIR/requirements.txt"
echo "  Dependencies installed"

# Stop existing service if running
if launchctl list | grep -q "$PLIST_NAME"; then
    echo -e "${BLUE}Stopping existing watcher service...${NC}"
    launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
fi

# Install launchd plist — only substitute the PROJECT_DIR placeholder. HF_TOKEN
# is NOT baked into the plist (audit #3); it flows in via ~/.whisper-env which
# the wrapper script sources at runtime.
echo -e "${BLUE}Installing launchd configuration...${NC}"
mkdir -p "$LAUNCH_AGENTS_DIR"

sed -e "s|/Users/davidmarchesseau/Development/whisper-transcription-app|$PROJECT_DIR|g" \
    "$PLIST_SRC" > "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "  Installed: $LAUNCH_AGENTS_DIR/$PLIST_NAME"

# Load the service
echo -e "${BLUE}Starting watcher service...${NC}"
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

# Verify it's running
sleep 2
if launchctl list | grep -q "com.whisper.jpr-watcher"; then
    echo -e "${GREEN}Watcher service is running!${NC}"
else
    echo -e "${YELLOW}Warning: Service may not have started correctly${NC}"
    echo -e "${YELLOW}Check logs: tail -f ~/Library/Logs/whisper/jpr-watcher.log${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "The watcher will now:"
echo "  - Start automatically on login"
echo "  - Monitor Just Press Record for new recordings"
echo "  - Transcribe new .m4a files automatically"
echo "  - Save .txt transcripts next to the recordings"
echo ""
echo "Commands:"
echo "  View logs:     tail -f ~/Library/Logs/whisper/jpr-watcher.log"
echo "  Stop service:  launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo "  Start service: launchctl load ~/Library/LaunchAgents/$PLIST_NAME"
echo "  Uninstall:     ./scripts/uninstall-watcher.sh"
echo ""
echo -e "${YELLOW}Note: Make sure the transcription backend is running:${NC}"
echo "  ./scripts/start-backend.sh"
echo ""

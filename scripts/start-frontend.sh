#!/bin/bash
#
# Whisper Transcription Frontend Startup Script
# Runs the React development server
#
# Usage: ./scripts/start-frontend.sh [backend_url]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Backend URL (default to localhost, or pass as argument)
BACKEND_URL="${1:-http://localhost:8000}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Whisper Transcription Frontend${NC}"
echo -e "${BLUE}========================================${NC}"

cd "$PROJECT_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing npm dependencies...${NC}"
    npm install
fi

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo ""
echo -e "${GREEN}Starting React development server...${NC}"
echo -e "${BLUE}Local:   ${NC}http://localhost:3000"
echo -e "${BLUE}Network: ${NC}http://$LOCAL_IP:3000"
echo -e "${BLUE}Backend: ${NC}$BACKEND_URL"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start with backend URL configured
export REACT_APP_API_URL="$BACKEND_URL"
exec npm start

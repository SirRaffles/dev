#!/bin/bash
#
# Stop all Davrine Transcription services
#
# Usage: ./scripts/stop-all.sh
#

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping Davrine Transcription services...${NC}"

# Kill backend (uvicorn)
pkill -f "uvicorn main:app" 2>/dev/null && echo "Backend stopped" || echo "Backend not running"

# Kill frontend (react-scripts)
pkill -f "react-scripts start" 2>/dev/null && echo "Frontend stopped" || echo "Frontend not running"

# Kill node processes on port 3000
lsof -ti:3000 | xargs kill 2>/dev/null || true

# Kill python processes on port 8000
lsof -ti:8000 | xargs kill 2>/dev/null || true

echo -e "${GREEN}All services stopped${NC}"

#!/bin/bash
#
# Start both Frontend and Backend for local development
# Runs everything on your MacBook
#
# Usage: ./scripts/start-all.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Whisper Transcription App${NC}"
echo -e "${BLUE}  Full Local Development Mode${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo -e "${GREEN}Starting services...${NC}"
echo ""
echo -e "${BLUE}Frontend: ${NC}http://localhost:3000"
echo -e "${BLUE}Backend:  ${NC}http://localhost:8000"
echo -e "${BLUE}Network:  ${NC}http://$LOCAL_IP:3000"
echo ""

# Create a temporary directory for logs
LOG_DIR="/tmp/whisper-transcription"
mkdir -p "$LOG_DIR"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $(jobs -p) 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend in background
echo -e "${YELLOW}Starting backend...${NC}"
"$SCRIPT_DIR/start-backend.sh" > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to initialize...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}Backend ready!${NC}"
        break
    fi
    sleep 2
done

# Start frontend in background
echo -e "${YELLOW}Starting frontend...${NC}"
"$SCRIPT_DIR/start-frontend.sh" > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}All services started!${NC}"
echo -e "${BLUE}Logs: ${NC}$LOG_DIR/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Wait for both processes
wait

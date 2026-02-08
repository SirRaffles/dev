#!/bin/bash
#
# Whisper Transcription Backend Startup Script
# Runs the FastAPI backend with Whisper on your MacBook M3
#
# Usage: ./scripts/start-backend.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Whisper Transcription Backend${NC}"
echo -e "${BLUE}========================================${NC}"

# Check for HuggingFace token
if [ -z "$HF_TOKEN" ]; then
    if [ -f "$PROJECT_DIR/.env" ]; then
        source "$PROJECT_DIR/.env"
    fi
fi

if [ -z "$HF_TOKEN" ]; then
    echo -e "${YELLOW}Warning: HF_TOKEN not set. Speaker diarization will be disabled.${NC}"
    echo -e "${YELLOW}Get your token at: https://huggingface.co/settings/tokens${NC}"
    echo ""
    read -p "Enter HuggingFace token (or press Enter to skip): " HF_TOKEN
    if [ -n "$HF_TOKEN" ]; then
        export HF_TOKEN
        echo "HF_TOKEN=$HF_TOKEN" > "$PROJECT_DIR/.env"
        echo -e "${GREEN}Token saved to .env file${NC}"
    fi
fi

# Use Python 3.11 for best compatibility with ML packages
PYTHON_CMD=""
for py in python3.11 python3.12 python3; do
    if command -v $py &> /dev/null; then
        PYTHON_CMD=$py
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.11+ is required${NC}"
    exit 1
fi

# Check for Python virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating Python virtual environment with $PYTHON_CMD...${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check if dependencies are installed
if ! python -c "import faster_whisper" 2>/dev/null; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install --upgrade pip
    pip install -r "$BACKEND_DIR/requirements.txt"
fi

# Check for ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}Error: ffmpeg is not installed${NC}"
    echo -e "${YELLOW}Install with: brew install ffmpeg${NC}"
    exit 1
fi

# Get local IP for network access
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo ""
echo -e "${GREEN}Starting Whisper backend server...${NC}"
echo -e "${BLUE}Local:   ${NC}http://localhost:8000"
echo -e "${BLUE}Network: ${NC}http://$LOCAL_IP:8000"
echo ""
echo -e "${YELLOW}First startup will download Whisper model (~3GB)${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start the server
cd "$BACKEND_DIR"
exec uvicorn main:app --host "${UVICORN_HOST:-127.0.0.1}" --port 8000

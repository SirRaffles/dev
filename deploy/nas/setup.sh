#!/bin/bash
#
# NAS Deployment Setup Script
# Run this on your Ugreen DXP 4800 Plus
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - Network access to your MacBook
#
# Usage:
#   1. Copy the entire project to your NAS
#   2. cd /path/to/whisper-transcription-app/deploy/nas
#   3. ./setup.sh <macbook-ip>
#
# Example:
#   ./setup.sh 192.168.1.100
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MACBOOK_IP="${1:-}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Whisper Transcription - NAS Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for MacBook IP
if [ -z "$MACBOOK_IP" ]; then
    echo -e "${YELLOW}Enter your MacBook's IP address:${NC}"
    read -p "> " MACBOOK_IP
fi

if [ -z "$MACBOOK_IP" ]; then
    echo -e "${RED}Error: MacBook IP is required${NC}"
    echo "Usage: $0 <macbook-ip>"
    exit 1
fi

BACKEND_URL="http://$MACBOOK_IP:8000"

# Test connection to MacBook backend
echo -e "${YELLOW}Testing connection to MacBook backend...${NC}"
if curl -s --connect-timeout 5 "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Backend is reachable!${NC}"
else
    echo -e "${YELLOW}Warning: Cannot reach backend at $BACKEND_URL${NC}"
    echo -e "${YELLOW}Make sure the backend is running on your MacBook${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Export backend URL
export BACKEND_URL

echo ""
echo -e "${YELLOW}Building and starting frontend container...${NC}"

# Build and start
docker-compose down 2>/dev/null || true
docker-compose build --build-arg REACT_APP_API_URL="$BACKEND_URL"
docker-compose up -d

# Get NAS IP
NAS_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Frontend URL:${NC} http://$NAS_IP:3000"
echo -e "${BLUE}Backend URL:${NC}  $BACKEND_URL"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  View logs:    docker-compose logs -f"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart"
echo "  Rebuild:      docker-compose up -d --build"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  Make sure your MacBook backend is running:"
echo "  cd /path/to/project && ./scripts/start-backend.sh"

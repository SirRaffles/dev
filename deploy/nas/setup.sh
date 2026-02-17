#!/bin/bash
#
# NAS Deployment Setup Script with Wake-on-LAN Support
# Run this on your Ugreen DXP 4800 Plus
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - Network access to your MacBook (LAN)
#
# Usage:
#   1. Copy the entire project to your NAS
#   2. cd /path/to/whisper-transcription-app/deploy/nas
#   3. ./setup.sh <macbook-ip> [macbook-mac-address]
#
# Example:
#   ./setup.sh 192.168.50.155 16:60:3e:7b:01:32
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MACBOOK_IP="${1:-}"
MACBOOK_MAC="${2:-16:60:3e:7b:01:32}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Whisper Transcription - NAS Setup${NC}"
echo -e "${BLUE}  (with Wake-on-LAN support)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for MacBook IP
if [ -z "$MACBOOK_IP" ]; then
    echo -e "${YELLOW}Enter your MacBook's IP address:${NC}"
    read -p "> " MACBOOK_IP
fi

if [ -z "$MACBOOK_IP" ]; then
    echo -e "${RED}Error: MacBook IP is required${NC}"
    echo "Usage: $0 <macbook-ip> [macbook-mac-address]"
    exit 1
fi

BACKEND_URL="http://$MACBOOK_IP:8000"

# Test connection to MacBook backend
echo -e "${YELLOW}Testing connection to MacBook backend...${NC}"
if curl -s --connect-timeout 5 "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Backend is reachable!${NC}"
else
    echo -e "${YELLOW}Warning: Cannot reach backend at $BACKEND_URL${NC}"
    echo -e "${YELLOW}This is OK if the Mac is sleeping — the wake proxy will handle it.${NC}"
    read -p "Continue anyway? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 1
    fi
fi

# Write .env for docker-compose
cat > .env << EOF
MAC_BACKEND_URL=$BACKEND_URL
MAC_MAC_ADDRESS=$MACBOOK_MAC
EOF

echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Backend URL:  $BACKEND_URL"
echo -e "  MAC Address:  $MACBOOK_MAC"
echo ""

echo -e "${YELLOW}Building and starting containers...${NC}"

# Build and start
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
docker compose up -d --build 2>/dev/null || docker-compose up -d --build

# Get NAS IP
NAS_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-nas-ip")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Frontend URL:${NC}  http://$NAS_IP:3000"
echo -e "${BLUE}Wake Proxy:${NC}   http://$NAS_IP:8080 (internal)"
echo -e "${BLUE}Backend URL:${NC}  $BACKEND_URL (on Mac)"
echo -e "${BLUE}MAC Address:${NC}  $MACBOOK_MAC"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  View logs:    docker compose logs -f"
echo "  Stop:         docker compose down"
echo "  Restart:      docker compose restart"
echo "  Rebuild:      docker compose up -d --build"
echo ""
echo -e "${YELLOW}How it works:${NC}"
echo "  When you submit a transcription and the Mac is sleeping,"
echo "  the wake proxy will automatically send a Wake-on-LAN packet"
echo "  and wait for the Mac to come online (~90 seconds)."
echo ""
echo -e "${YELLOW}Mac requirements:${NC}"
echo "  Ensure WoL is enabled: pmset -g | grep womp  (should show 1)"
echo "  Recommended: sudo pmset -a networkoversleep 1"
echo ""

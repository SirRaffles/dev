#!/bin/bash
#
# Davrine Transcription Frontend - Production Static Server
# Serves the React build directory on port 3000
#
# Usage: ./scripts/start-frontend-prod.sh
#

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build"

# Check build exists
if [ ! -d "$BUILD_DIR" ]; then
    echo "Error: build directory not found. Run 'npm run build' first." >&2
    exit 1
fi

# Use npx to run serve (auto-downloads if needed)
cd "$PROJECT_DIR"
exec /opt/homebrew/opt/node@18/bin/npx serve -s build -l 3000

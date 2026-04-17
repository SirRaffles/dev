#!/bin/bash
# Watcher launcher — sources secrets from ~/.whisper-env, then delegates to health-check script
# Used by launchd (com.whisper.jpr-watcher) to avoid plaintext secrets in plist
set -eo pipefail
source ~/.whisper-env
export HF_TOKEN="$HF_TOKEN_WATCHER"
export PYTHONUNBUFFERED=1
exec /Users/davidmarchesseau/Development/apps/whisper-transcription-app/scripts/start-watcher-with-health-check.sh "$@"

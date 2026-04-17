#!/bin/bash
# Backend launcher — sources secrets from ~/.whisper-env
# Used by launchd (com.whisper.backend) to avoid plaintext secrets in plist
set -eo pipefail
source ~/.whisper-env
export HF_TOKEN API_KEY PYTHONUNBUFFERED=1
exec /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

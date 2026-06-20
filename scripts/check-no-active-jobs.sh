#!/bin/bash
#
# Pre-deploy guard: exit non-zero if the backend has any in-flight
# transcription jobs, so `launchctl kickstart` doesn't orphan them.
#
# Usage:   ./scripts/check-no-active-jobs.sh [--quiet]
# Deploy:  ./scripts/check-no-active-jobs.sh && \
#            launchctl kickstart -k gui/$(id -u)/com.whisper.backend
#
# Exits 0 if the queue is clear (safe to restart) or the backend is down.
# Exits 2 if any job is in `pending` or `processing` state.
#

set -euo pipefail

QUIET=0
if [ "${1:-}" = "--quiet" ]; then QUIET=1; fi

HEALTH_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || echo 000)
if [ "$HEALTH_CODE" != "200" ]; then
  # Backend not reachable → nothing to orphan. Safe to proceed.
  [ "$QUIET" = 0 ] && echo "backend not reachable (health=$HEALTH_CODE) — safe to restart"
  exit 0
fi

# Ask the jobs API for the most recent rows and count active ones.
ACTIVE=$(curl -s "http://127.0.0.1:8000/jobs?limit=30" 2>/dev/null \
  | /usr/bin/env python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(0); sys.exit(0)
count = sum(1 for j in d.get('jobs', []) if j.get('status') in ('processing', 'pending'))
print(count)
")

if [ "${ACTIVE:-0}" -gt 0 ]; then
  echo "ABORT: $ACTIVE active transcription job(s) — restart would orphan them." >&2
  echo "Wait for completion, or \`DELETE /job/{id}\` them first if abandoning." >&2
  curl -s "http://127.0.0.1:8000/jobs?limit=30" 2>/dev/null \
    | /usr/bin/env python3 -c "
import json, sys
d = json.load(sys.stdin)
for j in d.get('jobs', []):
    if j.get('status') in ('processing', 'pending'):
        print(f\"  {j['status']:10} {j['progress']:3}%  {j['progress_message'][:50]}  id={j['job_id'][:8]}\")
" >&2
  exit 2
fi

[ "$QUIET" = 0 ] && echo "queue clear — safe to restart"
exit 0

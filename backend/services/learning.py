"""Continuous learning system (B7).

After each refined transcription, three failure-isolated workers run:
- update_speaker_embeddings: EMA-merge fresh voice embeddings into the registry
- extract_insights_auto: refresh per-speaker insights from the new transcript
- learn_glossary_terms: surface high-confidence corrections as pending-review terms

Every action appends a structured event to learning_log.jsonl on iCloud (with
fcntl LOCK_EX + fsync for crash-safety across concurrent writers).
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import ICLOUD_BASE_PATH

logger = logging.getLogger(__name__)

LEARNING_LOG_PATH: Path = ICLOUD_BASE_PATH / "learning_log.jsonl"


def _utc_iso_z() -> str:
    """RFC 3339 / ISO 8601 UTC timestamp with second precision (e.g. 2026-05-15T13:51:39Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_event(event_type: str, **fields) -> None:
    """Append one JSON line to learning_log.jsonl on iCloud.

    Holds fcntl.LOCK_EX for the duration of write + fsync to serialize
    concurrent writers (iCloud has no atomic-append guarantees).

    Never raises — logs and returns on any IO/lock failure.
    """
    if not event_type:
        return
    record = {"ts": _utc_iso_z(), "type": event_type, **fields}
    payload = json.dumps(record, ensure_ascii=False) + "\n"

    try:
        LEARNING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEARNING_LOG_PATH, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
    except OSError as exc:
        logger.warning("learning: record_event(%s) failed: %s", event_type, exc)

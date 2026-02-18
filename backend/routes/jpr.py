"""
Just Press Record (JPR) file management API routes.
Browse iCloud JPR recordings and their transcription status.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException

from config import JPR_WATCH_PATH, JPR_STATE_FILE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jpr"])


def _load_watcher_state() -> dict:
    """Load the watcher state file."""
    if not JPR_STATE_FILE.exists():
        return {}
    try:
        return json.loads(JPR_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _recording_status(file_path: str, watcher_state: dict) -> dict:
    """Determine the processing status of a recording from watcher state."""
    # The watcher state keys on the filename or full path
    for key, entry in watcher_state.items():
        if key == file_path or key.endswith(os.path.basename(file_path)):
            return {
                "status": entry.get("status", "unknown"),
                "job_id": entry.get("job_id"),
                "transcript_path": entry.get("transcript_path"),
                "error": entry.get("error"),
                "submitted_at": entry.get("submitted_at"),
                "completed_at": entry.get("completed_at"),
            }
    return {"status": "unprocessed", "job_id": None}


@router.get("/jpr/recordings")
async def list_recordings(
    limit: int = 50,
    offset: int = 0,
    status: str = "all",
):
    """List JPR recordings from iCloud with their processing status."""
    if not JPR_WATCH_PATH.exists():
        return {
            "recordings": [],
            "total": 0,
            "watcher_status": {"available": False, "error": "JPR iCloud folder not found"},
        }

    watcher_state = _load_watcher_state()

    recordings = []
    for f in sorted(JPR_WATCH_PATH.rglob("*.m4a"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            stat = f.stat()
            file_status = _recording_status(str(f), watcher_state)

            # Filter by status
            if status != "all" and file_status["status"] != status:
                continue

            # Check if transcript exists
            txt_path = f.with_suffix(".txt")
            transcript_exists = txt_path.exists()

            recordings.append({
                "filename": f.name,
                "path": str(f.relative_to(JPR_WATCH_PATH)),
                "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_bytes": stat.st_size,
                "transcript_exists": transcript_exists,
                **file_status,
            })
        except OSError:
            continue

    total = len(recordings)
    recordings = recordings[offset:offset + limit]

    # Compute watcher summary
    state_entries = watcher_state.values() if isinstance(watcher_state, dict) else []
    completed = sum(1 for e in state_entries if isinstance(e, dict) and e.get("status") == "completed")
    pending = sum(1 for e in state_entries if isinstance(e, dict) and e.get("status") in ("pending_submission", "processing"))
    failed = sum(1 for e in state_entries if isinstance(e, dict) and e.get("status") in ("failed", "permanently_failed"))

    return {
        "recordings": recordings,
        "total": total,
        "watcher_status": {
            "available": True,
            "total_tracked": len([e for e in state_entries if isinstance(e, dict)]),
            "completed": completed,
            "pending": pending,
            "failed": failed,
        },
    }


@router.get("/jpr/recordings/{path:path}")
async def get_recording(path: str):
    """Get details about a specific recording including transcript if available."""
    file_path = JPR_WATCH_PATH / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    # Security: ensure path is within JPR folder
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(JPR_WATCH_PATH.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    stat = file_path.stat()
    watcher_state = _load_watcher_state()
    file_status = _recording_status(str(file_path), watcher_state)

    # Read transcript if exists
    transcript_text = None
    txt_path = file_path.with_suffix(".txt")
    if txt_path.exists():
        try:
            transcript_text = txt_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass

    return {
        "filename": file_path.name,
        "path": path,
        "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_bytes": stat.st_size,
        "transcript_exists": transcript_text is not None,
        "transcript_text": transcript_text,
        **file_status,
    }


@router.post("/jpr/recordings/{path:path}/reprocess")
async def reprocess_recording(path: str):
    """Reset a recording's watcher state to trigger re-transcription."""
    file_path = JPR_WATCH_PATH / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    # Security check
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(JPR_WATCH_PATH.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    # Remove from watcher state to allow re-processing
    watcher_state = _load_watcher_state()
    str_path = str(file_path)

    removed = False
    keys_to_remove = []
    for key in watcher_state:
        if key == str_path or key.endswith(os.path.basename(str_path)):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del watcher_state[key]
        removed = True

    if removed:
        # Write updated state atomically
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=JPR_STATE_FILE.parent,
            suffix=".tmp", delete=False,
        )
        try:
            json.dump(watcher_state, tmp, indent=2)
            tmp.close()
            os.replace(tmp.name, str(JPR_STATE_FILE))
        except Exception:
            os.unlink(tmp.name)
            raise

    return {"status": "queued" if removed else "not_tracked", "path": path}

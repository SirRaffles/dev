"""
Just Press Record (JPR) file management API routes.
Browse iCloud JPR recordings and their transcription status, with
filter / sort / search / rename / transcript access.
"""

import os
import re
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Body

from config import JPR_WATCH_PATH, JPR_STATE_FILE
import state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jpr"])

# Validated, safe filenames (no slashes, no NUL, sensible chars).
_FILENAME_RE = re.compile(r"^[A-Za-z0-9 _.,'()\-]{1,200}$")

# Preview length for per-recording transcript snippet in list response.
_PREVIEW_CHARS = 240
# Hard cap on files scanned per list request to prevent abuse.
_MAX_SCAN_FILES = 10_000


def _load_watcher_state() -> dict:
    if not JPR_STATE_FILE.exists():
        return {}
    try:
        return json.loads(JPR_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_watcher_state(watcher_state: dict) -> None:
    """Atomic write of the watcher state file."""
    JPR_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", dir=JPR_STATE_FILE.parent,
        suffix=".tmp", delete=False,
    )
    try:
        json.dump(watcher_state, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, str(JPR_STATE_FILE))
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _find_watcher_entry_key(file_path: str, watcher_state: dict) -> Optional[str]:
    """Return the watcher-state key that matches the file path, or None."""
    base = os.path.basename(file_path)
    for key in watcher_state:
        if key == file_path or key.endswith(base):
            return key
    return None


def _recording_status(file_path: str, watcher_state: dict) -> dict:
    """Determine the processing status of a recording from watcher state."""
    key = _find_watcher_entry_key(file_path, watcher_state)
    if key is None:
        return {
            "status": "unprocessed",
            "job_id": None,
            "transcript_path": None,
            "error": None,
            "submitted_at": None,
            "completed_at": None,
        }
    entry = watcher_state.get(key, {})
    return {
        "status": entry.get("status", "unknown"),
        "job_id": entry.get("job_id"),
        "transcript_path": entry.get("transcript_path"),
        "error": entry.get("error"),
        "submitted_at": entry.get("submitted_at"),
        "completed_at": entry.get("completed_at"),
    }


def _safe_resolve(rel_path: str) -> Path:
    """Resolve a user-supplied relative path under JPR_WATCH_PATH safely."""
    if ".." in rel_path.split("/"):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    target = (JPR_WATCH_PATH / rel_path).resolve()
    if not str(target).startswith(str(JPR_WATCH_PATH.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return target


# Map the simplified UI "processed" label to the watcher's "completed" status.
_STATUS_ALIASES = {
    "processed": "completed",
    "processing": "processing",
    "pending": "pending_submission",
    "failed": "failed",
    "unprocessed": "unprocessed",
    "all": "all",
}


def _read_transcript_preview(file_path: Path) -> Optional[str]:
    """Return the first _PREVIEW_CHARS of the sibling .txt file, if present."""
    txt_path = file_path.with_suffix(".txt")
    if not txt_path.exists():
        return None
    try:
        with txt_path.open("r", encoding="utf-8", errors="ignore") as f:
            return f.read(_PREVIEW_CHARS * 4)  # read extra so search has room
    except OSError:
        return None


def _read_full_transcript(file_path: Path) -> Optional[str]:
    """Read the full sibling .txt file."""
    txt_path = file_path.with_suffix(".txt")
    if not txt_path.exists():
        return None
    try:
        return txt_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _job_speakers(job_id: Optional[str]) -> list:
    """Return distinct speaker labels from a job's segments, if reachable."""
    if not job_id:
        return []
    try:
        job = state.jobs.get(job_id)
        if not job:
            return []
        seen = set()
        labels = []
        for seg in getattr(job, "segments", []) or []:
            sp = seg.get("speaker") if isinstance(seg, dict) else None
            if sp and sp not in seen:
                seen.add(sp)
                labels.append(sp)
        return labels
    except Exception:
        return []


@router.get("/jpr/recordings")
async def list_recordings(
    limit: int = 50,
    offset: int = 0,
    status: str = "all",
    sort_by: str = "date",   # "date" (recording mtime) or "completed_at"
    sort_dir: str = "desc",
    q: Optional[str] = None,  # free-text search across filename + transcript + speakers
):
    """List JPR recordings with filter/sort/search.

    - status: all | unprocessed | processed | processing | failed (aliases mapped)
    - sort_by: date | completed_at   (descending unless sort_dir=asc)
    - q: substring match on filename OR transcript text OR speaker labels
    """
    if not JPR_WATCH_PATH.exists():
        return {
            "recordings": [],
            "total": 0,
            "watcher_status": {"available": False, "error": "JPR iCloud folder not found"},
        }

    if len(q or "") > 200:
        raise HTTPException(status_code=400, detail="Search query too long")

    watcher_state = _load_watcher_state()
    wanted = _STATUS_ALIASES.get(status, status)
    query = (q or "").strip().lower()

    # Walk the tree once. Gather everything first; we sort + filter + paginate
    # in memory because this scales fine for typical JPR usage (O(hundreds) of
    # files) and we need full transcript access for search anyway.
    entries = []
    scanned = 0
    for f in JPR_WATCH_PATH.rglob("*.m4a"):
        scanned += 1
        if scanned > _MAX_SCAN_FILES:
            logger.warning("JPR scan hit cap at %d files", _MAX_SCAN_FILES)
            break
        try:
            stat = f.stat()
        except OSError:
            continue

        file_status = _recording_status(str(f), watcher_state)
        txt_preview_full = _read_transcript_preview(f) if query else None
        transcript_exists = f.with_suffix(".txt").exists()
        speakers = _job_speakers(file_status.get("job_id")) if file_status.get("job_id") else []

        # UI-facing "effective" status: a file with a sibling .txt is
        # functionally processed even if the watcher never tracked it (e.g.
        # web-UI uploads don't update watcher_state). Keeps the badge/icon
        # rendering consistent with the filter logic.
        raw_status = file_status.get("status", "unprocessed")
        if raw_status == "completed" or transcript_exists:
            effective_status = "completed"
        elif raw_status in ("pending_submission", "processing"):
            effective_status = "processing"
        elif raw_status in ("failed", "permanently_failed"):
            effective_status = "failed"
        else:
            effective_status = "unprocessed"

        entries.append({
            "filename": f.name,
            "path": str(f.relative_to(JPR_WATCH_PATH)),
            "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_bytes": stat.st_size,
            "transcript_exists": transcript_exists,
            "transcript_preview": (txt_preview_full[:_PREVIEW_CHARS] if txt_preview_full else None),
            "speakers": speakers,
            "effective_status": effective_status,
            **file_status,
        })

        # Keep the long preview off the response; we only used it for search.
        if query:
            entries[-1]["_search_corpus"] = " ".join(filter(None, [
                f.name.lower(),
                (txt_preview_full or "").lower(),
                " ".join(speakers).lower(),
            ]))

    # Status filter. Note: a file may have been transcribed via the web UI
    # without updating the watcher state, so treat transcript_exists as a
    # "processed" signal in addition to the watcher's "completed".
    if wanted not in ("all",):
        if wanted == "unprocessed":
            entries = [
                e for e in entries
                if e["status"] == "unprocessed" and not e.get("transcript_exists")
            ]
        elif wanted == "completed":
            entries = [
                e for e in entries
                if e["status"] == "completed" or e.get("transcript_exists")
            ]
        elif wanted == "processing":
            entries = [e for e in entries if e["status"] in ("processing", "pending_submission")]
        elif wanted == "failed":
            entries = [e for e in entries if e["status"] in ("failed", "permanently_failed")]
        else:
            entries = [e for e in entries if e["status"] == wanted]

    # Search filter
    if query:
        entries = [e for e in entries if query in e.pop("_search_corpus", "")]
    else:
        # Make sure the scratch field is gone.
        for e in entries:
            e.pop("_search_corpus", None)

    # Sort
    reverse = sort_dir.lower() != "asc"
    if sort_by == "completed_at":
        entries.sort(
            key=lambda e: e.get("completed_at") or "",
            reverse=reverse,
        )
    else:
        entries.sort(
            key=lambda e: e.get("date") or "",
            reverse=reverse,
        )

    total = len(entries)
    recordings = entries[offset:offset + limit]

    # Watcher summary stats (computed over the full raw state, not filtered).
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


@router.get("/jpr/recordings/{path:path}/transcript")
async def get_recording_transcript(path: str):
    """Return the full transcript (from .txt + job record if available)."""
    file_path = _safe_resolve(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    watcher_state = _load_watcher_state()
    file_status = _recording_status(str(file_path), watcher_state)

    transcript_text = _read_full_transcript(file_path)
    segments: list = []
    speakers: list = []
    language: Optional[str] = None

    job_id = file_status.get("job_id")
    if job_id:
        try:
            job = state.jobs.get(job_id)
            if job and getattr(job, "segments", None):
                segments = job.segments
                speakers = _job_speakers(job_id)
                language = getattr(job, "language", None)
        except Exception:
            pass

    return {
        "path": path,
        "filename": file_path.name,
        "transcript_text": transcript_text,
        "segments": segments,
        "speakers": speakers,
        "language": language,
        "job_id": job_id,
        "status": file_status.get("status"),
    }


@router.get("/jpr/recordings/{path:path}")
async def get_recording(path: str):
    """Get details about a specific recording including transcript if available."""
    file_path = _safe_resolve(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    stat = file_path.stat()
    watcher_state = _load_watcher_state()
    file_status = _recording_status(str(file_path), watcher_state)

    transcript_text = _read_full_transcript(file_path)

    return {
        "filename": file_path.name,
        "path": path,
        "date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_bytes": stat.st_size,
        "transcript_exists": transcript_text is not None,
        "transcript_text": transcript_text,
        "speakers": _job_speakers(file_status.get("job_id")),
        **file_status,
    }


@router.post("/jpr/recordings/{path:path}/rename")
async def rename_recording(path: str, body: dict = Body(...)):
    """Rename a recording (and its sibling .txt if present). Updates watcher
    state keys that reference the old path."""
    new_name = (body.get("new_name") or "").strip()
    if not _FILENAME_RE.match(new_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid new_name. Use letters, digits, spaces, and ._-,'() only (max 200 chars).",
        )

    file_path = _safe_resolve(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    # Preserve the .m4a extension; let the user type the basename only.
    new_stem = new_name.rsplit(".m4a", 1)[0] if new_name.lower().endswith(".m4a") else new_name
    new_filename = f"{new_stem}.m4a"
    new_path = file_path.with_name(new_filename)

    if new_path == file_path:
        return {"status": "unchanged", "path": path}

    if new_path.exists():
        raise HTTPException(status_code=409, detail="A file with that name already exists in this folder")

    # Rename audio
    try:
        file_path.rename(new_path)
    except OSError as e:
        logger.error("Rename failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Rename failed")

    # Rename sibling .txt if present
    old_txt = file_path.with_suffix(".txt")
    new_txt = new_path.with_suffix(".txt")
    if old_txt.exists() and not new_txt.exists():
        try:
            old_txt.rename(new_txt)
        except OSError:
            logger.warning("Failed to rename sibling transcript for %s", path, exc_info=True)

    # Update watcher state keys that reference the old path
    watcher_state = _load_watcher_state()
    old_str = str(file_path)
    new_str = str(new_path)
    updated_keys = []
    rekey_pairs = []
    for key, entry in list(watcher_state.items()):
        if key == old_str or key.endswith(file_path.name):
            rekey_pairs.append((key, entry))
    for key, entry in rekey_pairs:
        if isinstance(entry, dict):
            # Rewrite transcript_path if it pointed at the old .txt
            tp = entry.get("transcript_path")
            if tp and os.path.basename(tp) == old_txt.name:
                entry["transcript_path"] = str(new_txt)
        watcher_state.pop(key, None)
        watcher_state[new_str if key == old_str else new_str] = entry
        updated_keys.append(key)

    if updated_keys:
        try:
            _write_watcher_state(watcher_state)
        except Exception:
            logger.warning("Failed to persist renamed watcher state", exc_info=True)

    new_rel = str(new_path.relative_to(JPR_WATCH_PATH))
    return {"status": "renamed", "old_path": path, "new_path": new_rel}


@router.post("/jpr/recordings/{path:path}/reprocess")
async def reprocess_recording(path: str):
    """Reset a recording's watcher state to trigger re-transcription."""
    file_path = _safe_resolve(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    watcher_state = _load_watcher_state()
    str_path = str(file_path)

    keys_to_remove = []
    for key in watcher_state:
        if key == str_path or key.endswith(os.path.basename(str_path)):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del watcher_state[key]

    if keys_to_remove:
        _write_watcher_state(watcher_state)

    return {"status": "queued" if keys_to_remove else "not_tracked", "path": path}

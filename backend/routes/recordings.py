"""
Unified recordings endpoint — merges JPR-discovered files with direct uploads.

The Recordings tab in the UI used to list only files watched under
JPR_WATCH_PATH. Direct uploads (via the "Upload File" button or YouTube
ingest) lived in the job store but never showed up there. This module
unifies both into a single list, tagged with a `source` field so the UI
can render an appropriate badge.

De-duplication: a job whose settings.original_filename matches a JPR
file already in the list is dropped (the JPR row has richer metadata —
transcript_preview, speakers, etc.).
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from config import JPR_WATCH_PATH
import app_state
from routes.jpr import list_recordings as _jpr_list_recordings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recordings"])


def _job_is_jpr(meta: Optional[dict]) -> bool:
    """True iff this job's audio resolves under JPR_WATCH_PATH.

    Conservative: if anything is ambiguous (missing settings, unresolvable
    path), return False so the job is treated as a direct upload and the
    user still sees it. The JPR-side listing handles dedup by filename.
    """
    if not meta:
        return False
    settings = meta.get("settings") or {}
    original = settings.get("original_filename")
    if not original:
        return False
    try:
        # If the basename matches anything under JPR_WATCH_PATH, treat as JPR.
        # We don't need a full path resolve — the JPR listing already includes
        # everything under JPR_WATCH_PATH, so any name-match means the dedup
        # check on the merged list will catch it.
        for _ in JPR_WATCH_PATH.rglob(original):
            return True
    except (OSError, ValueError):
        return False
    return False


@router.get("/recordings")
async def list_recordings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str = "all",
    sort_by: str = "date",
    sort_dir: str = "desc",
    q: Optional[str] = Query(None, max_length=200),
):
    """Return JPR files + direct uploads as a unified, source-tagged list.

    Mirrors the filter/sort/search params of /jpr/recordings so the frontend
    hook can swap to this endpoint with no UI-state changes.

    Each row carries a `source` field:
      - "jpr"     : discovered by the JPR iCloud watcher
      - "upload"  : direct file upload (via UI or API)
      - "youtube" : YouTube URL ingest
    """
    # Delegate JPR listing to the existing endpoint so we never drift from
    # its filter/sort/search semantics. It already returns dicts.
    jpr_response = await _jpr_list_recordings(
        limit=limit,
        offset=0,                # apply offset/limit AFTER merge below
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        q=q,
    )
    jpr_items = list(jpr_response.get("recordings") or [])
    watcher_status = jpr_response.get("watcher_status") or {}

    # Tag JPR rows explicitly.
    for r in jpr_items:
        r.setdefault("source", "jpr")

    # Build the dedup set: filename basenames the JPR list already covers.
    jpr_filenames = {r.get("filename") for r in jpr_items if r.get("filename")}

    # Pull recent jobs — wider than `limit` since we'll filter out JPR-backed
    # ones. 5× headroom is a sane upper bound for typical job volumes.
    job_summaries = app_state.jobs().list_recent(limit=max(limit * 5, 200), offset=0)

    upload_items: list = []
    for js in job_summaries:
        job_id = js.get("job_id")
        if not job_id:
            continue
        _jobs = app_state.jobs()
        meta = _jobs.get_job_meta(job_id) if hasattr(_jobs, "get_job_meta") else None
        settings = (meta or {}).get("settings") or {}
        youtube_url = (meta or {}).get("youtube_url")

        # Skip JPR-backed jobs entirely; the JPR side covers them.
        if _job_is_jpr(meta):
            continue

        # Determine the display filename. For YouTube jobs there's no file,
        # so fall back to the URL.
        original = settings.get("original_filename") or js.get("file_path")
        if not original and youtube_url:
            original = youtube_url
        if not original:
            continue  # can't display this row meaningfully

        # Dedup against JPR filenames (defensive — _job_is_jpr should catch most).
        if original in jpr_filenames:
            continue

        source = "youtube" if youtube_url else "upload"
        job_status = js.get("status") or "unprocessed"

        # Map raw job status -> UI effective_status (same vocabulary as JPR rows).
        if job_status == "completed":
            effective_status = "completed"
        elif job_status in ("processing", "pending", "pending_submission"):
            effective_status = "processing"
        elif job_status in ("failed", "permanently_failed"):
            effective_status = "failed"
        else:
            effective_status = "unprocessed"

        # For YouTube jobs, keep the URL verbatim as the display name.
        # For uploads, strip any path component.
        display_name = original if youtube_url else Path(original).name
        upload_items.append({
            "filename": display_name,
            "path": (meta or {}).get("file_path") or "",
            "date": js.get("created_at"),
            "size_bytes": 0,
            "status": job_status,
            "effective_status": effective_status,
            "job_id": job_id,
            "transcript_exists": job_status == "completed",
            "transcript_preview": None,
            "speakers": [],
            "submitted_at": js.get("created_at"),
            "completed_at": js.get("updated_at") if job_status == "completed" else None,
            "error": None,
            "transcript_path": None,
            "source": source,
        })

    # Apply the status filter to direct-upload rows (JPR side already filtered).
    if status and status not in ("all", ""):
        if status in ("processed", "completed"):
            upload_items = [u for u in upload_items if u["effective_status"] == "completed"]
        elif status == "processing":
            upload_items = [u for u in upload_items if u["effective_status"] == "processing"]
        elif status == "failed":
            upload_items = [u for u in upload_items if u["effective_status"] == "failed"]
        elif status == "unprocessed":
            # Direct uploads always carry a job record, so "unprocessed" (which
            # in JPR terms means "audio file with no job at all") excludes them.
            upload_items = []

    # Apply the search filter (filename only — uploads have no transcript text here).
    if q:
        needle = q.strip().lower()
        if needle:
            upload_items = [u for u in upload_items if needle in (u.get("filename") or "").lower()]

    # Merge and sort. Use the same sort vocabulary as the JPR endpoint.
    merged = jpr_items + upload_items
    reverse = sort_dir.lower() != "asc"
    if sort_by == "completed_at":
        merged.sort(key=lambda r: r.get("completed_at") or "", reverse=reverse)
    else:
        merged.sort(key=lambda r: r.get("date") or "", reverse=reverse)

    total = len(merged)
    page = merged[offset:offset + limit]

    return {
        "recordings": page,
        "total": total,
        "watcher_status": watcher_status,
    }

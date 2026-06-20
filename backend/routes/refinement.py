"""
Transcript refinement API routes.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import PlainTextResponse

import app_state
import state  # noqa: F401 — re-exported so tests can monkeypatch refmod.state.* (reach-through to the real state module read live by app_state)
from utils.export import format_timestamp

# The refinement dispatch + worker path lives in the service layer: S5 moved
# dispatch (so the orchestrator dispatches without importing a route); the F1
# follow-up moved the workers + cleanup helper too (so the service no longer
# imports this route at all). Re-exported here so endpoint wrappers, cross-route
# callers, and tests keep working via `from routes.refinement import _run_...`.
from services.refinement_dispatch import (  # noqa: F401
    dispatch_refinement_for_job,
    _set_refinement_status,
    _run_refinement_for_job,
    _run_post_refinement_learning,
    _cleanup_deferred_audio,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refine", tags=["refinement"])


def _run_refinement(job_id: str):
    """Backwards-compatible wrapper: manual route resolves audio for B7."""
    # Lazy import to avoid pulling routes.transcription at module load.
    try:
        from routes.transcription import _resolve_job_audio_path
        audio_path = _resolve_job_audio_path(job_id)
    except Exception:
        audio_path = None
    _run_refinement_for_job(job_id, speaker_ids=None, context_path=None,
                            audio_path=audio_path)


@router.post("/job/{job_id}")
async def start_refinement(job_id: str, background_tasks: BackgroundTasks):
    """Start transcript refinement for a completed transcription job."""
    if not app_state.refinement_available():
        raise HTTPException(status_code=503, detail="Refinement not available (claude CLI not found)")

    # Check job exists
    job = app_state.job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job status is '{job.status}', must be 'completed'")

    if not job.segments:
        raise HTTPException(status_code=400, detail="Job has no segments to refine")

    # Check if refinement already exists
    existing = app_state.refinement_store().get(job_id)
    if existing and existing["status"] == "processing":
        return {"job_id": job_id, "status": "processing", "message": "Refinement already in progress"}

    try:
        from routes.transcription import _resolve_job_audio_path
        audio_path = _resolve_job_audio_path(job_id)
    except Exception:
        audio_path = None
    try:
        dispatch_refinement_for_job(job, speaker_ids=None, context_path=None, audio_path=audio_path)
    except Exception as exc:
        logger.exception("Manual refinement dispatch failed for %s", job_id)
        raise HTTPException(status_code=500, detail=f"Failed to start refinement: {exc}")

    return {"job_id": job_id, "status": "pending", "message": "Refinement started"}


@router.get("/job/{job_id}")
async def get_refinement_status(job_id: str):
    """Get refinement status and results."""
    if not app_state.refinement_available():
        raise HTTPException(status_code=503, detail="Refinement not available")

    refinement = app_state.refinement_store().get(job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="No refinement found for this job")

    return refinement


@router.get("/job/{job_id}/export")
async def export_refined_transcript(
    job_id: str,
    format: str = Query("txt", description="Export format (txt)"),
):
    """Export the refined transcript as plain text."""
    if not app_state.refinement_available():
        raise HTTPException(status_code=503, detail="Refinement not available")

    refinement = app_state.refinement_store().get(job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="No refinement found for this job")

    if refinement["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Refinement status is '{refinement['status']}'")

    segments = refinement.get("refined_segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="No refined segments available")

    # Generate text output
    lines = []
    for seg in segments:
        parts = []
        ts = format_timestamp(seg.get("start", 0))
        parts.append(f"[{ts}]")
        speaker = seg.get("speaker")
        if speaker:
            parts.append(f"{speaker}:")
        parts.append(seg.get("text", "").strip())
        lines.append(" ".join(parts))

    text = "\n".join(lines)

    return PlainTextResponse(content=text, media_type="text/plain; charset=utf-8")


@router.post("/batch")
async def batch_refine(
    job_ids: List[str],
    background_tasks: BackgroundTasks,
):
    """Start refinement for multiple completed jobs."""
    if not app_state.refinement_available():
        raise HTTPException(status_code=503, detail="Refinement not available")

    results = []
    for job_id in job_ids:
        job = app_state.job_store().get(job_id)
        if not job:
            results.append({"job_id": job_id, "status": "error", "message": "Job not found"})
            continue
        if job.status != "completed":
            results.append({"job_id": job_id, "status": "error", "message": f"Job status is '{job.status}'"})
            continue
        if not job.segments:
            results.append({"job_id": job_id, "status": "error", "message": "No segments"})
            continue

        # Check if already refined
        existing = app_state.refinement_store().get(job_id)
        if existing and existing["status"] == "completed":
            results.append({"job_id": job_id, "status": "already_completed"})
            continue

        app_state.refinement_store().create(job_id)
        background_tasks.add_task(_run_refinement, job_id)
        results.append({"job_id": job_id, "status": "started"})

    return {"results": results, "total": len(job_ids), "started": sum(1 for r in results if r["status"] == "started")}

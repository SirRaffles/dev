"""
Transcript refinement API routes.
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import PlainTextResponse

import state
from utils.export import format_timestamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refine", tags=["refinement"])


def _run_refinement(job_id: str):
    """Background task to run refinement on a completed transcription job."""
    try:
        state.refinement_store.update_status(job_id, "processing")

        # Get the original job's segments
        job = state.job_store.get(job_id)
        if not job:
            state.refinement_store.update_status(job_id, "failed", "Job not found")
            return

        if job.status != "completed":
            state.refinement_store.update_status(job_id, "failed", f"Job status is '{job.status}', not 'completed'")
            return

        if not job.segments:
            state.refinement_store.update_status(job_id, "failed", "Job has no segments")
            return

        # Run refinement
        result = state.refinement_service.refine(job.segments)

        # Save result
        state.refinement_store.save_result(job_id, result)
        logger.info("Refinement complete for job %s", job_id)

    except Exception as e:
        logger.exception("Refinement failed for job %s", job_id)
        state.refinement_store.update_status(job_id, "failed", str(e))


@router.post("/job/{job_id}")
async def start_refinement(job_id: str, background_tasks: BackgroundTasks):
    """Start transcript refinement for a completed transcription job."""
    if not state.refinement_available:
        raise HTTPException(status_code=503, detail="Refinement not available (claude CLI not found)")

    # Check job exists
    job = state.job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job status is '{job.status}', must be 'completed'")

    if not job.segments:
        raise HTTPException(status_code=400, detail="Job has no segments to refine")

    # Check if refinement already exists
    existing = state.refinement_store.get(job_id)
    if existing and existing["status"] == "processing":
        return {"job_id": job_id, "status": "processing", "message": "Refinement already in progress"}

    # Create refinement entry
    state.refinement_store.create(job_id)

    # Start background task
    background_tasks.add_task(_run_refinement, job_id)

    return {"job_id": job_id, "status": "pending", "message": "Refinement started"}


@router.get("/job/{job_id}")
async def get_refinement_status(job_id: str):
    """Get refinement status and results."""
    if not state.refinement_available:
        raise HTTPException(status_code=503, detail="Refinement not available")

    refinement = state.refinement_store.get(job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="No refinement found for this job")

    return refinement


@router.get("/job/{job_id}/export")
async def export_refined_transcript(
    job_id: str,
    format: str = Query("txt", description="Export format (txt)"),
):
    """Export the refined transcript as plain text."""
    if not state.refinement_available:
        raise HTTPException(status_code=503, detail="Refinement not available")

    refinement = state.refinement_store.get(job_id)
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
    if not state.refinement_available:
        raise HTTPException(status_code=503, detail="Refinement not available")

    results = []
    for job_id in job_ids:
        job = state.job_store.get(job_id)
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
        existing = state.refinement_store.get(job_id)
        if existing and existing["status"] == "completed":
            results.append({"job_id": job_id, "status": "already_completed"})
            continue

        state.refinement_store.create(job_id)
        background_tasks.add_task(_run_refinement, job_id)
        results.append({"job_id": job_id, "status": "started"})

    return {"results": results, "total": len(job_ids), "started": sum(1 for r in results if r["status"] == "started")}

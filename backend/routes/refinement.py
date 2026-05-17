"""
Transcript refinement API routes.
"""

import logging
import os
import shutil
import tempfile
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import PlainTextResponse

import state
from utils.export import format_timestamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refine", tags=["refinement"])


def _set_refinement_status(job, status: str) -> None:
    """Mirror refinement_status onto the in-memory job and persist via state.jobs.update.

    Logs (debug) and swallows on persistence failure -- the in-memory attribute
    is what UI polls.
    """
    if job is None:
        return
    job.refinement_status = status
    try:
        state.jobs.update(job)
    except Exception:
        logger.debug("jobs.update mirror failed for job %s", job.job_id, exc_info=True)


def _cleanup_deferred_audio(audio_path: Optional[str]) -> None:
    """Delete the tmp audio file (and its tmp parent dir) that
    _run_transcription_sync deferred to us. No-op when audio_path is None,
    when the path is gone, or when it's outside /tmp."""
    if not audio_path:
        return
    try:
        parent_dir = os.path.dirname(audio_path)
        if parent_dir and os.path.isdir(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(parent_dir, ignore_errors=True)
        elif os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        logger.debug("B7 audio cleanup failed for %s", audio_path, exc_info=True)


def _run_post_refinement_learning(job_id: str, audio_path: Optional[str],
                                  segments: list, analysis: dict) -> None:
    """B7 orchestrator: run the three learning workers, aggregate status.

    Each worker is wrapped in its own try/except — one failure must not block
    the others. Sets job.learning_summary + job.learning_status, then persists
    via state.jobs.update.
    """
    from services import learning

    # Build {pyannote_label_or_name: speaker_name} from refined segments.
    # After refinement, segments use real speaker names instead of SPEAKER_XX
    # (or keep SPEAKER_XX if neither B5 nor refinement could identify them).
    assignments: dict = {}
    for seg in (segments or []):
        spk = (seg.get("speaker") or "").strip()
        if not spk or spk.startswith("SPEAKER_"):
            continue
        assignments[spk] = spk  # key=name, value=name (we no longer have the original label)

    # B7 follow-up: overlay refined speaker names back into job.segments so
    # extract_insights_auto (which reads job.segments via the existing
    # _extract_speaker_insights_sync helper) sees real names instead of
    # SPEAKER_XX. Build a {(start,end): refined_speaker} map from segment
    # timings, then mutate job.segments in place.
    # Use state.jobs (alias of state.job_store) for consistency with the
    # surrounding orchestrator body (lines below).
    job_for_overlay = state.jobs.get(job_id)
    if job_for_overlay is not None and job_for_overlay.segments and segments:
        refined_by_span = {
            (round(float(s.get("start", 0)), 2),
             round(float(s.get("end", 0)), 2)): s.get("speaker")
            for s in segments if s.get("speaker")
        }
        overlaid = False
        for raw in job_for_overlay.segments:
            key = (round(float(raw.get("start", 0)), 2),
                   round(float(raw.get("end", 0)), 2))
            new_spk = refined_by_span.get(key)
            if new_spk and new_spk != raw.get("speaker"):
                raw["speaker"] = new_spk
                overlaid = True
        if overlaid:
            try:
                state.jobs.update(job_for_overlay)
            except Exception:
                logger.debug("jobs.update after overlay failed for %s",
                             job_id, exc_info=True)

    # Prefer pyannote's raw turn boundaries (higher precision: 30s+ continuous
    # speech blocks) over per-utterance segments (3-10s each). Both B5 and the
    # diarization step populate job.speakers with pyannote-shaped turns; fall
    # back to synthesizing from refined segments only if job.speakers is empty.
    # Use state.jobs (NOT state.job_store) — convention matches _run_transcription_sync.
    job_for_turns = state.jobs.get(job_id)
    raw_turns = (job_for_turns.speakers if job_for_turns is not None else None) or []
    if raw_turns:
        speaker_turns = [
            {"start": float(t.get("start", 0)),
             "end": float(t.get("end", 0)),
             "speaker": t.get("speaker", "")}
            for t in raw_turns
            if (t.get("speaker") or "").strip()
        ]
    else:
        speaker_turns = [
            {"start": float(seg.get("start", 0)),
             "end": float(seg.get("end", 0)),
             "speaker": seg.get("speaker", "")}
            for seg in (segments or [])
            if (seg.get("speaker") or "").strip()
        ]

    successes = 0
    emb_count = ins_count = glo_count = 0

    try:
        emb_count = learning.update_speaker_embeddings(
            job_id=job_id, audio_path=audio_path,
            speaker_turns=speaker_turns, assignments=assignments,
        )
        successes += 1
    except Exception:
        logger.exception("B7 embedding worker failed for job %s", job_id)

    try:
        ins_count = learning.extract_insights_auto(job_id=job_id)
        successes += 1
    except Exception:
        logger.exception("B7 insight worker failed for job %s", job_id)

    try:
        glo_count = learning.learn_glossary_terms(
            job_id=job_id, corrections=(analysis or {}).get("corrections", []),
        )
        successes += 1
    except Exception:
        logger.exception("B7 glossary worker failed for job %s", job_id)

    # Use state.jobs (same convention as _run_transcription_sync). state.job_store
    # is an alias bound at module load, but monkeypatching one in tests does NOT
    # update the other — so be consistent with the writer-side convention.
    job = state.jobs.get(job_id)
    if job is not None:
        job.learning_summary = {
            "embeddings_updated": emb_count,
            "insights_added": ins_count,
            "terms_learned": glo_count,
        }
        if successes == 3:
            job.learning_status = "ok"
        elif successes >= 1:
            job.learning_status = "partial"
        else:
            job.learning_status = "failed"
        try:
            state.jobs.update(job)
        except Exception:
            logger.debug("jobs.update mirror failed for job %s", job_id, exc_info=True)


def _run_refinement_for_job(job_id: str, speaker_ids: Optional[List[str]] = None,
                            context_path: Optional[str] = None,
                            audio_path: Optional[str] = None):
    """Run refinement for a completed job with the given context bundle.

    Loads the same context sources transcription used (global glossary +
    context_path + speaker bios) and feeds them to RefinementService.refine.
    Updates the job's refinement_status and the RefinementStore row.
    Calls B7 learning orchestrator at the tail of the success branch.
    """
    # Local imports to avoid circular load: services.glossary imports
    # derive_context_terms from services.transcription, so importing them at
    # module load creates a cycle.
    from services.transcription import (
        load_context_document,
        load_speakers_context,
        merge_context_sources,
    )
    from services.glossary import load_global_glossary, load_global_glossary_terms

    job = state.job_store.get(job_id)
    if not job:
        state.refinement_store.update_status(job_id, "failed", "Job not found")
        return

    try:
        state.refinement_store.update_status(job_id, "processing")
        _set_refinement_status(job, "processing")

        if job.status != "completed":
            state.refinement_store.update_status(
                job_id, "failed", f"Job status is '{job.status}', not 'completed'"
            )
            _set_refinement_status(job, "failed")
            return

        if not job.segments:
            state.refinement_store.update_status(job_id, "failed", "Job has no segments")
            _set_refinement_status(job, "failed")
            return

        # Augment the user's pre-picked speaker_ids with anyone B5 voice
        # auto-match identified. Without this, the user has to manually pick
        # both speakers up front for refinement to know who they are — even
        # though the system has already figured it out acoustically.
        # B5 results live on job.auto_speaker_matches (Plan 1 Task 9 + the
        # Plan 3 Task 2 segment overlay propagates the names but not the IDs).
        matched_ids: List[str] = []
        if job.auto_speaker_matches:
            for m in job.auto_speaker_matches.values():
                sid = m.get("speaker_id") if isinstance(m, dict) else None
                if m and m.get("matched") and sid:
                    matched_ids.append(sid)
        effective_speaker_ids: List[str] = list({*(speaker_ids or []), *matched_ids})

        context_text = merge_context_sources(
            load_global_glossary(),
            load_context_document(context_path),
            load_speakers_context(effective_speaker_ids or None),
        )
        glossary_terms = load_global_glossary_terms() or None

        # Build pyannote turn list for Combo C semantic diarization polish.
        # Same shape and source as _run_post_refinement_learning uses (job.speakers
        # is the pyannote diarization output set by transcription.py). Falls back
        # to deriving turns from job.segments when job.speakers is empty (e.g.
        # diarization was disabled or failed).
        raw_turns = (job.speakers or [])
        if raw_turns:
            speaker_turns = [
                {"start": float(t.get("start", 0)),
                 "end": float(t.get("end", 0)),
                 "speaker": (t.get("speaker") or "").strip()}
                for t in raw_turns
                if (t.get("speaker") or "").strip()
            ]
        else:
            speaker_turns = [
                {"start": float(seg.get("start", 0)),
                 "end": float(seg.get("end", 0)),
                 "speaker": (seg.get("speaker") or "").strip()}
                for seg in (job.segments or [])
                if (seg.get("speaker") or "").strip()
            ]

        result = state.refinement_service.refine(
            job.segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
            speaker_turns=speaker_turns or None,
        )
        state.refinement_store.save_result(job_id, result)
        _set_refinement_status(job, "done")
        logger.info("Refinement complete for job %s", job_id)

        # B7: post-refinement learning. Best-effort — never raises.
        try:
            _run_post_refinement_learning(
                job_id=job_id,
                audio_path=audio_path,
                segments=result.get("refined_segments", job.segments),
                analysis=result.get("analysis", {}),
            )
        except Exception:
            logger.exception("B7 orchestrator outer failure for job %s", job_id)

    except Exception as e:
        logger.exception("Refinement failed for job %s", job_id)
        state.refinement_store.update_status(job_id, "failed", str(e))
        _set_refinement_status(job, "failed")
    finally:
        # B7 deferred cleanup: _run_transcription_sync skipped tmp-audio cleanup
        # when it dispatched us (job._defer_audio_cleanup=True). We own the
        # cleanup now — runs on success path, refine-failure path, and
        # orchestrator-failure path alike. If audio_path is None (manual route,
        # or audio already gone), this is a no-op.
        _cleanup_deferred_audio(audio_path)


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

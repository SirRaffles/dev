"""
Call management API routes.
Handles the call lifecycle: speaker identification, context assignment, deliverable generation.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["calls"])


class ConfirmSpeakerRequest(BaseModel):
    speaker_label: str
    speaker_name: str
    create_new: bool = False


class AssignContextRequest(BaseModel):
    context_path: str


class CallTitleRequest(BaseModel):
    title: str


class RegisterCallRequest(BaseModel):
    source_type: str = "upload"
    source_path: Optional[str] = None
    title: Optional[str] = None


@router.get("/calls")
async def list_calls(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
):
    """List calls with their lifecycle status."""
    calls = state.call_metadata_store.list_recent(limit, offset, status)
    # Enrich with speaker info
    for call in calls:
        speakers = state.call_speaker_store.get_for_call(call["job_id"])
        call["speakers"] = speakers
    return {"calls": calls, "total": state.call_metadata_store.count(status)}


@router.get("/calls/{job_id}")
async def get_call(job_id: str):
    """Get full call detail including speakers, context, deliverables."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    speakers = state.call_speaker_store.get_for_call(job_id)

    # Check readiness
    missing = []
    if not call.get("speakers_identified"):
        missing.append("speakers")
    if not call.get("context_assigned"):
        missing.append("context")

    return {
        **call,
        "speaker_identifications": speakers,
        "readiness": {
            "ready": len(missing) == 0,
            "missing": missing,
        },
    }


@router.post("/calls/{job_id}/register")
async def register_call(job_id: str, req: RegisterCallRequest):
    """Register a completed transcription as a call."""
    # Verify job exists
    job = state.job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create or get existing call metadata
    existing = state.call_metadata_store.get(job_id)
    if existing:
        return existing

    result = state.call_metadata_store.create(
        job_id=job_id,
        source_type=req.source_type,
        source_path=req.source_path,
        title=req.title,
    )
    return result


@router.put("/calls/{job_id}/title")
async def set_call_title(job_id: str, req: CallTitleRequest):
    """Set or update a call's title."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    state.call_metadata_store.update(job_id, title=req.title)
    return {"status": "updated", "title": req.title}


@router.put("/calls/{job_id}/context")
async def assign_context(job_id: str, req: AssignContextRequest):
    """Assign a context folder to a call."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    state.call_metadata_store.update(
        job_id,
        context_path=req.context_path,
        context_assigned=1,
    )
    return {"status": "assigned", "context_path": req.context_path}


# Speaker identification and deliverable generation endpoints will be
# implemented in Phase 2 (speaker_embedding.py) and Phase 6 (deliverable_service.py)
# and wired in here. Placeholder endpoints below.


@router.post("/calls/{job_id}/identify-speakers")
async def identify_speakers(job_id: str):
    """Trigger automatic speaker identification via voice embeddings."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Get the job's diarization results
    job = state.job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcription job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before identifying speakers")
    if not job.speakers:
        raise HTTPException(status_code=400, detail="No diarization data available for this job")

    # Get audio path — check job metadata for file_path or source_path
    audio_path = call.get("source_path")
    if not audio_path:
        meta = state.job_store.get_job_meta(job_id)
        audio_path = meta.get("file_path") if meta else None
    if not audio_path:
        raise HTTPException(
            status_code=400,
            detail="Audio file path not available (needed for embedding extraction)"
        )

    try:
        embedding_service = state.get_speaker_embedding_service()
        identifications = embedding_service.auto_identify_speakers(
            audio_path, job.speakers, job_id
        )

        # Save results to call_speakers table
        state.call_speaker_store.delete_for_call(job_id)  # Clear previous
        for label, ident in identifications.items():
            if ident.get("speaker_id"):
                state.call_speaker_store.add(
                    call_id=job_id,
                    speaker_id=ident["speaker_id"],
                    speaker_label=label,
                    confidence=ident["confidence"],
                )

        # Check if all speakers are auto-matched
        all_matched = all(i.get("matched") for i in identifications.values())
        if all_matched:
            state.call_metadata_store.update(job_id, speakers_identified=1)

        return {"identifications": identifications, "all_matched": all_matched}

    except Exception as e:
        logger.error("Speaker identification failed for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Speaker identification failed. Please try again.")


@router.post("/calls/{job_id}/confirm-speaker")
async def confirm_speaker(job_id: str, req: ConfirmSpeakerRequest):
    """Confirm or correct a speaker identification."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    job = state.job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    speaker_name = req.speaker_name.strip()
    if not speaker_name:
        raise HTTPException(status_code=400, detail="Speaker name is required")

    embedding_service = state.get_speaker_embedding_service()

    # Find or create the speaker
    speaker = state.speaker_store.get_by_name(speaker_name)
    if not speaker and req.create_new:
        # Try to get the unknown embedding for this label
        unknown_emb = embedding_service.get_unknown_embedding(req.speaker_label, job_id)
        if unknown_emb is not None:
            speaker_id = embedding_service.register_speaker(speaker_name, unknown_emb)
        else:
            # Create speaker without embedding (can be added later)
            import uuid
            speaker_id = str(uuid.uuid4())
            from config import ICLOUD_BASE_PATH
            folder = ICLOUD_BASE_PATH / "speakers" / speaker_name
            folder.mkdir(parents=True, exist_ok=True)
            folder_path = str(folder.relative_to(ICLOUD_BASE_PATH))
            # Initialize personality.md
            (folder / "personality.md").write_text(
                f"# {speaker_name}\n\n*No personality insights yet.*\n",
                encoding="utf-8",
            )
            state.speaker_store.create(speaker_id, speaker_name, folder_path)
        speaker = state.speaker_store.get_by_name(speaker_name)
    elif not speaker:
        raise HTTPException(
            status_code=404,
            detail=f"Speaker '{speaker_name}' not found. Set create_new=true to create."
        )

    # Update the call-speaker association
    state.call_speaker_store.add(
        call_id=job_id,
        speaker_id=speaker["speaker_id"],
        speaker_label=req.speaker_label,
        confidence=1.0,  # User-confirmed = 100%
    )
    state.call_speaker_store.confirm(job_id, speaker["speaker_id"])

    # Update the speaker's embedding with the new sample (if available)
    unknown_emb = embedding_service.get_unknown_embedding(req.speaker_label, job_id)
    if unknown_emb is not None:
        embedding_service.update_embedding(speaker_name, unknown_emb)

    # Update speaker stats
    # Calculate speaking time for this speaker in the call
    speaking_time = sum(
        t["end"] - t["start"]
        for t in (job.speakers or [])
        if t.get("speaker") == req.speaker_label
    )
    state.speaker_store.increment_call_count(speaker["speaker_id"], speaking_time)

    # Also rename the speaker in the transcript segments
    if job.segments:
        for seg in job.segments:
            if seg.get("speaker") == req.speaker_label:
                seg["speaker"] = speaker_name
        state.job_store.update(job)

    # Check if all speakers are now confirmed
    if state.call_speaker_store.all_confirmed(job_id):
        state.call_metadata_store.update(job_id, speakers_identified=1)

    return {
        "speaker_id": speaker["speaker_id"],
        "name": speaker_name,
        "confirmed": True,
        "all_speakers_confirmed": state.call_speaker_store.all_confirmed(job_id),
    }


@router.post("/calls/{job_id}/generate-deliverables")
async def generate_deliverables(job_id: str):
    """Generate summary and analysis deliverables for a call."""
    if not state.deliverable_available:
        raise HTTPException(status_code=503, detail="Deliverable generation not available (claude CLI not found)")

    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.get("speakers_identified"):
        raise HTTPException(status_code=400, detail="Speakers must be identified first")
    if not call.get("context_assigned"):
        raise HTTPException(status_code=400, detail="Context must be assigned first")

    try:
        results = state.deliverable_service.generate_deliverables(job_id)
        return {
            "status": "generated",
            "call_folder": results.get("call_folder"),
            "generated": results.get("generated", []),
            "errors": results.get("errors", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Deliverable generation failed for %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Deliverable generation failed. Please try again.")


@router.get("/calls/{job_id}/deliverables")
async def get_deliverables(job_id: str):
    """Read generated deliverables for a call."""
    call = state.call_metadata_store.get(job_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.get("deliverables_generated"):
        return {"summary_md": None, "analysis_md": None, "generated": False}

    # Read from call folder on iCloud Drive
    from config import ICLOUD_BASE_PATH
    call_folder = ICLOUD_BASE_PATH / call.get("call_folder_path", "")

    summary_md = ""
    analysis_md = ""
    if (call_folder / "summary.md").exists():
        summary_md = (call_folder / "summary.md").read_text(encoding="utf-8")
    if (call_folder / "analysis.md").exists():
        analysis_md = (call_folder / "analysis.md").read_text(encoding="utf-8")

    return {
        "summary_md": summary_md,
        "analysis_md": analysis_md,
        "generated": True,
        "generated_at": call.get("deliverables_generated_at"),
    }

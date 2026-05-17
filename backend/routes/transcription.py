"""
Transcription API routes: file upload, YouTube, batch, job management, export.
"""

import io
import json
import os
import uuid
import shutil
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Literal

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse

from config import (
    SUPPORTED_LANGUAGES, ALLOWED_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS,
)
from job_models import (
    TranscriptionJob, BatchJob, TranscriptionSettings,
    YouTubeRequest, SpeakerRenameRequest, SegmentUpdate,
)
from services.audio import extract_audio
from services.youtube import download_youtube_audio, extract_video_id, get_youtube_transcript
from services.transcription import transcribe_audio
from utils.export import generate_txt, generate_markdown, generate_srt, generate_vtt, generate_pdf, generate_docx, generate_json_export
import state

logger = logging.getLogger(__name__)

router = APIRouter()

# Plan 4A: accepted engine values (mirror of TranscriptionSettings.engine Literal).
_VALID_ENGINES = frozenset({"auto-best", "auto-quick"})


def _validate_engine_or_400(engine: str) -> None:
    """Hard-reject legacy engine values. The frontend was updated in lockstep
    (Sub-plan C); any old client gets a clear 400 telling it what to send."""
    if engine in _VALID_ENGINES:
        return
    raise HTTPException(
        status_code=400,
        detail=(
            f"Engine {engine!r} is no longer supported. "
            f"Use 'auto-best' or 'auto-quick'."
        ),
    )


def _validate_file_magic(file_path: str, expected_ext: str) -> bool:
    """Validate file content matches expected type via magic bytes."""
    MAGIC_SIGNATURES = {
        # Audio formats
        ".wav": [(0, b"RIFF")],
        ".mp3": [(0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2"), (0, b"ID3")],
        ".flac": [(0, b"fLaC")],
        ".ogg": [(0, b"OggS")],
        ".m4a": [(4, b"ftyp")],
        ".aac": [(0, b"\xff\xf1"), (0, b"\xff\xf9")],
        # Video formats
        ".mp4": [(4, b"ftyp")],
        ".mkv": [(0, b"\x1a\x45\xdf\xa3")],
        ".avi": [(0, b"RIFF")],
        ".webm": [(0, b"\x1a\x45\xdf\xa3")],
        ".mov": [(4, b"ftyp")],
    }

    sigs = MAGIC_SIGNATURES.get(expected_ext)
    if not sigs:
        return True  # No known signature for this extension

    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        return any(
            len(header) > offset and header[offset:offset + len(sig)] == sig
            for offset, sig in sigs
        )
    except OSError:
        return False


async def _extract_audio_then_transcribe(
    job_id: str,
    input_path: str,
    audio_path: str,
    remove_input_after: bool,
    settings: TranscriptionSettings,
):
    """Background task: run blocking extract_audio off the event loop, then transcribe (audit #8)."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, extract_audio, input_path, audio_path)
        if remove_input_after:
            try:
                os.remove(input_path)
            except OSError:
                pass
    except Exception as exc:
        logger.error("extract_audio failed for job %s", job_id, exc_info=True)
        job = state.jobs.get(job_id)
        if job is not None:
            job.status = "failed"
            job.error = f"Audio extraction failed: {exc}"
            state.jobs.update(job)
        return
    await transcribe_audio(job_id, audio_path, settings)


@router.post("/transcribe/file")
async def transcribe_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language code: en, fr, or auto"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    enable_noise_reduction: bool = Query(False, description="Apply noise reduction before transcription"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps (slower but more precise)"),
    translate_to_english: bool = Query(False, description="Translate output to English (any language -> English)"),
    engine: str = Query("auto-best", description="Quality mode: 'auto-best' or 'auto-quick'"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms (advisory)"),
    context_path: Optional[str] = Query(None, description="Path under CONTEXTS_DIR to a .md context document"),
    output_mode: str = Query("verbatim", description="Output mode: verbatim (raw) or readable (cleaned, sentence-segmented)"),
):
    """Upload and transcribe an audio/video file with speaker diarization."""
    if output_mode not in ("verbatim", "readable"):
        raise HTTPException(status_code=400, detail="Invalid output_mode. Use: verbatim, readable")

    _validate_engine_or_400(engine)

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)

    file_ext = Path(file.filename).suffix.lower() if file.filename else ".tmp"
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    temp_dir = tempfile.mkdtemp(prefix="whisper-upload-")
    input_path = os.path.join(temp_dir, f"input{file_ext}")

    max_size = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500")) * 1024 * 1024

    try:
        file_size = 0
        with open(input_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > max_size:
                    f.close()
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB."
                    )
                f.write(chunk)

        # Validate magic bytes match declared file type
        if not _validate_file_magic(input_path, file_ext):
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match declared type '{file_ext}'"
            )

        # Audit #8: do NOT call extract_audio inline — push it into the background task
        # so the HTTP response can return immediately with job_id.
        audio_path = os.path.join(temp_dir, "audio.wav")
        if file_ext in ALLOWED_AUDIO_EXTENSIONS:
            remove_input_after = False
        else:
            remove_input_after = True

        parsed_context_terms = None
        if context_terms:
            parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

        settings = TranscriptionSettings(
            vad_filter=False,
            word_timestamps=word_timestamps,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=enable_noise_reduction,
            translate_to_english=translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
            context_path=context_path,
            output_mode=output_mode,
        )

        state.jobs.create(job, file_path=audio_path, settings=settings.model_dump())
        background_tasks.add_task(
            _extract_audio_then_transcribe,
            job_id, input_path, audio_path, remove_input_after, settings,
        )

        return {"job_id": job_id, "status": "processing", "engine": engine}

    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/transcribe/youtube")
async def transcribe_youtube(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks,
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers"),
    use_captions: bool = Query(True, description="Try YouTube captions first"),
    engine: str = Query("auto-best", description="Quality mode: 'auto-best' or 'auto-quick'"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms (advisory)"),
    context_path: Optional[str] = Query(None, description='Path under CONTEXTS_DIR to a .md context document'),
    output_mode: str = Query("verbatim", description="Output mode: verbatim (raw) or readable (cleaned, sentence-segmented)"),
):
    """Download and transcribe audio from a YouTube URL."""
    # Fail fast with 400 (not 500) on malformed URLs — checks the canonical
    # YOUTUBE_URL_RE before any download/captions work.
    from services.youtube import YOUTUBE_URL_RE
    if not YOUTUBE_URL_RE.match(request.url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    if output_mode not in ("verbatim", "readable"):
        raise HTTPException(status_code=400, detail="Invalid output_mode. Use: verbatim, readable")

    _validate_engine_or_400(engine)

    if request.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    state.jobs.create(job, youtube_url=request.url)

    video_id = extract_video_id(request.url)

    if use_captions and video_id:
        job.status = "processing"
        job.progress_message = "Checking for YouTube captions..."

        transcript = get_youtube_transcript(video_id, request.language)

        if transcript:
            segments = transcript["segments"]

            # Apply readable-mode postprocessing to captions
            if output_mode == "readable":
                from services.postprocess import (
                    normalize_segments, apply_readable_mode, merge_caption_segments,
                )
                normalize_segments(segments)
                # Merge caption display-lines into full sentences with paragraph breaks
                segments = merge_caption_segments(segments)
                # Apply text transforms (filler removal, currency, sentence boundaries)
                # but skip gap-based paragraph detection (merge already added paragraph flags)
                apply_readable_mode(segments, detect_paragraphs=False)
                transcript["text"] = " ".join(
                    seg["text"].strip() for seg in segments if seg.get("text")
                )

            job.status = "completed"
            job.progress = 100
            job.progress_message = "Complete (YouTube captions)"
            job.segments = segments
            job.result = transcript["text"]
            job.language = transcript["language"]
            job.language_probability = 1.0
            # Surface is_generated so the frontend captions badge can reflect
            # whether these are human-authored or auto-generated captions.
            job.is_generated = bool(transcript.get("is_generated", False))
            job._from_captions = True
            state.jobs.update(job)

            return {
                "job_id": job_id,
                "status": "completed",
                "source": "youtube_captions",
                "is_generated": transcript.get("is_generated", False),
                "language": transcript["language"],
                "segment_count": len(transcript["segments"]),
            }

    temp_dir = tempfile.mkdtemp(prefix="whisper-yt-")

    try:
        job.status = "processing"
        job.progress_message = "Downloading audio from YouTube..."
        state.jobs.update(job)

        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(
            None,
            download_youtube_audio,
            request.url,
            temp_dir
        )

        parsed_context_terms = None
        if context_terms:
            parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

        settings = TranscriptionSettings(
            vad_filter=False,
            word_timestamps=word_timestamps,
            language=request.language,
            enable_diarization=request.enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=request.enable_noise_reduction,
            translate_to_english=request.translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
            context_path=context_path,
            output_mode=output_mode,
        )

        # Persist settings for retry capability
        with state.jobs._lock:
            with state.jobs._get_connection() as conn:
                conn.execute(
                    "UPDATE jobs SET settings=? WHERE job_id=?",
                    (json.dumps(settings.model_dump()), job_id)
                )
                conn.commit()

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing", "engine": engine}

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        job.status = "failed"
        job.error = "YouTube transcription failed"
        state.jobs.update(job)
        logger.error(f"YouTube transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="YouTube transcription failed. The video may be unavailable or an internal error occurred.")


@router.post("/transcribe/batch")
async def transcribe_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    language: str = Query("auto", description="Language code"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    translate_to_english: bool = Query(False, description="Translate output to English"),
    engine: str = Query("auto-best", description="Quality mode: 'auto-best' or 'auto-quick'"),
    context_terms: Optional[str] = Query(None, description="Context terms (advisory)"),
    context_path: Optional[str] = Query(None, description='Path under CONTEXTS_DIR to a .md context document'),
    output_mode: str = Query("verbatim", description="Output mode: verbatim (raw) or readable (cleaned, sentence-segmented)"),
):
    """Upload and transcribe multiple audio/video files in batch."""
    if output_mode not in ("verbatim", "readable"):
        raise HTTPException(status_code=400, detail="Invalid output_mode. Use: verbatim, readable")

    _validate_engine_or_400(engine)

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    batch_id = str(uuid.uuid4())
    job_ids = []

    for file in files:
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(job_id)

        temp_dir = tempfile.mkdtemp(prefix="whisper-batch-")
        file_ext = Path(file.filename).suffix.lower() if file.filename else ".tmp"
        input_path = os.path.join(temp_dir, f"input{file_ext}")
        audio_path = os.path.join(temp_dir, "audio.wav")

        parsed_context_terms = None
        if context_terms:
            parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

        settings = TranscriptionSettings(
            vad_filter=False,
            word_timestamps=word_timestamps,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
            translate_to_english=translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
            context_path=context_path,
            output_mode=output_mode,
        )

        # Audit #6: persist via JobStore.create() BEFORE upload so an oversize
        # failure can persist job.status="failed" properly.
        state.jobs.create(job, file_path=audio_path, settings=settings.model_dump())
        job_ids.append(job_id)

        max_size = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500")) * 1024 * 1024

        try:
            file_size = 0
            oversize = False
            with open(input_path, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    file_size += len(chunk)
                    if file_size > max_size:
                        f.close()
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        job.status = "failed"
                        job.error = f"File too large. Maximum size is {max_size // (1024 * 1024)}MB."
                        state.jobs.update(job)
                        oversize = True
                        break
                    f.write(chunk)

            if oversize:
                continue

            audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
            remove_input_after = file_ext not in audio_extensions

            background_tasks.add_task(
                _extract_audio_then_transcribe,
                job_id, input_path, audio_path, remove_input_after, settings,
            )

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            job.status = "failed"
            job.error = str(e)
            state.jobs.update(job)

    batch = BatchJob(batch_id, job_ids)
    state.batch_jobs[batch_id] = batch

    return {
        "batch_id": batch_id,
        "job_ids": job_ids,
        "total": len(job_ids)
    }


@router.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get the status of a batch transcription job."""
    batch = state.batch_jobs.get(batch_id)

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    job_statuses = []
    completed_count = 0
    failed_count = 0
    processing_count = 0
    pending_count = 0

    for job_id in batch.job_ids:
        job = state.jobs.get(job_id)
        if job:
            job_status = {
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress,
            }

            if job.status == "completed":
                completed_count += 1
            elif job.status == "failed":
                failed_count += 1
                job_status["error"] = job.error
            elif job.status == "processing":
                processing_count += 1
            else:
                pending_count += 1

            job_statuses.append(job_status)

    total_progress = sum(state.jobs.get(jid).progress for jid in batch.job_ids if state.jobs.get(jid))
    overall_progress = int(total_progress / batch.total) if batch.total > 0 else 0

    if completed_count == batch.total:
        overall_status = "completed"
    elif failed_count == batch.total:
        overall_status = "failed"
    elif failed_count > 0 or processing_count > 0:
        overall_status = "processing"
    else:
        overall_status = "pending"

    return {
        "batch_id": batch.batch_id,
        "total": batch.total,
        "overall_status": overall_status,
        "overall_progress": overall_progress,
        "completed": completed_count,
        "failed": failed_count,
        "processing": processing_count,
        "pending": pending_count,
        "jobs": job_statuses,
    }


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(50, ge=1, le=200, description="Max jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, completed, failed"),
):
    """List recent transcription jobs with lightweight summaries."""
    jobs = state.jobs.list_recent(limit=limit, offset=offset, status=status)
    total = state.jobs.count(status=status)
    return {"jobs": jobs, "total": total, "limit": limit, "offset": offset}


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status and result of a transcription job."""
    job = state.jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "progress_message": job.progress_message,
        # Plan 4A: phase pill for phased progress bar
        "phase": getattr(job, "phase", None),
        # B2: surface auto-refine indicators for UI polling (None when not applicable)
        "refinement_status": getattr(job, "refinement_status", None),
        "auto_speaker_matches": getattr(job, "auto_speaker_matches", None),
        "learning_summary": getattr(job, "learning_summary", None),
        "learning_status": getattr(job, "learning_status", None),
        # Rename-source feature: original JPR filename (None for non-JPR jobs) +
        # ISO created_at so the rename modal can suggest "YYYY-MM-DD HH-MM — ..."
        "original_filename": getattr(getattr(job, "settings", None), "original_filename", None),
        "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
    }

    if job.status == "completed":
        # Derive source: captions fast-path jobs have the `_from_captions`
        # marker set; audio-engine jobs don't. Frontend uses this to pick
        # the right badge.
        source = "youtube_captions" if getattr(job, "_from_captions", False) else None
        response.update({
            "result": job.result,
            "segments": job.segments,
            "speakers": list(set(s.get("speaker") for s in job.segments if s.get("speaker"))),
            "language": job.language,
            "language_probability": job.language_probability,
            "is_generated": bool(getattr(job, "is_generated", False)),
            "source": source,
        })
    elif job.status == "failed":
        response["error"] = job.error

    return response


@router.get("/job/{job_id}/export")
async def export_transcript(
    job_id: str,
    format: Literal["txt", "md", "srt", "vtt", "json", "pdf", "docx"] = Query(..., description="Export format"),
):
    """Export transcript in various formats."""
    job = state.jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Transcription not completed")

    filename = f"transcript_{job_id[:8]}"

    if format == "txt":
        content = generate_txt(job)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}.txt"}
        )

    elif format == "md":
        content = generate_markdown(job)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={filename}.md"}
        )

    elif format == "srt":
        content = generate_srt(job)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}.srt"}
        )

    elif format == "vtt":
        content = generate_vtt(job)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/vtt",
            headers={"Content-Disposition": f"attachment; filename={filename}.vtt"}
        )

    elif format == "json":
        content = generate_json_export(job)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}.json"}
        )

    elif format == "pdf":
        content = generate_pdf(job)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}.pdf"}
        )

    elif format == "docx":
        content = generate_docx(job)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}.docx"}
        )


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a transcription job."""
    if job_id not in state.jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del state.jobs[job_id]
    return {"status": "deleted"}


@router.post("/job/{job_id}/retry")
async def retry_job(job_id: str, background_tasks: BackgroundTasks):
    """Retry a failed transcription job with the same settings."""
    meta = state.jobs.get_job_meta(job_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Job not found")

    original_job = state.jobs.get(job_id)
    if original_job and original_job.status not in ("failed",):
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    stored_settings = meta.get("settings")
    youtube_url = meta.get("youtube_url")
    file_path = meta.get("file_path")

    if stored_settings is None:
        raise HTTPException(
            status_code=400,
            detail="Original job settings not available. Please re-submit."
        )

    settings = TranscriptionSettings(**stored_settings)
    new_job_id = str(uuid.uuid4())
    new_job = TranscriptionJob(new_job_id)

    if youtube_url:
        # Re-download and transcribe YouTube
        temp_dir = tempfile.mkdtemp(prefix="whisper-yt-retry-")
        new_job.status = "downloading"
        new_job.progress_message = "Downloading audio from YouTube..."
        state.jobs.create(new_job, youtube_url=youtube_url, settings=stored_settings)
        try:
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None,
                download_youtube_audio,
                youtube_url,
                temp_dir
            )
            background_tasks.add_task(transcribe_audio, new_job_id, audio_path, settings)
            return {"job_id": new_job_id, "status": "processing", "retried_from": job_id}
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            new_job.status = "failed"
            new_job.error = str(e)
            state.jobs.update(new_job)
            logger.error(f"Retry YouTube error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Retry failed. The video may be unavailable or an internal error occurred.")
    else:
        # File-based job: check if temp file still exists AND that it lives under /tmp.
        # Audit #4: never re-read a stored path that escapes the system temp dir.
        if not file_path:
            raise HTTPException(status_code=410, detail="original upload no longer available")
        try:
            resolved = Path(file_path).resolve()
            if not resolved.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                raise HTTPException(status_code=410, detail="original upload no longer available")
        except (OSError, RuntimeError):
            raise HTTPException(status_code=410, detail="original upload no longer available")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=410, detail="original upload no longer available")
        state.jobs.create(new_job, file_path=file_path, settings=stored_settings)
        # Audit #16: mark job as a retry so the worker's cleanup guard can skip rmtree.
        setattr(new_job, "_retry_of", job_id)
        background_tasks.add_task(transcribe_audio, new_job_id, file_path, settings)
        return {"job_id": new_job_id, "status": "processing", "retried_from": job_id}


@router.put("/job/{job_id}/speakers")
async def rename_speakers(job_id: str, request: SpeakerRenameRequest):
    """Update speaker names in a transcription job."""
    job = state.jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before renaming speakers")

    if not request.speaker_mapping:
        raise HTTPException(status_code=400, detail="Speaker mapping cannot be empty")

    for segment in job.segments:
        if segment.get("speaker") and segment["speaker"] in request.speaker_mapping:
            segment["speaker"] = request.speaker_mapping[segment["speaker"]]

    for speaker_turn in job.speakers:
        if speaker_turn.get("speaker") and speaker_turn["speaker"] in request.speaker_mapping:
            speaker_turn["speaker"] = request.speaker_mapping[speaker_turn["speaker"]]

    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result,
        "segments": job.segments,
        "speakers": list(set(s.get("speaker") for s in job.segments if s.get("speaker"))),
        "language": job.language,
        "language_probability": job.language_probability,
    }


@router.put("/job/{job_id}/segments")
async def update_segments(job_id: str, request: SegmentUpdate):
    """Update transcript segments with inline edits."""
    job = state.jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before updating segments")

    if not request.segments:
        raise HTTPException(status_code=400, detail="Segments cannot be empty")

    required_fields = {"start", "end", "text"}
    for i, segment in enumerate(request.segments):
        if not all(field in segment for field in required_fields):
            raise HTTPException(
                status_code=400,
                detail=f"Segment {i} missing required fields. Required: {required_fields}"
            )

    job.segments = request.segments

    full_text_parts = [seg["text"].strip() for seg in job.segments if seg.get("text")]
    job.result = " ".join(full_text_parts)

    return {
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result,
        "segments": job.segments,
        "speakers": list(set(s.get("speaker") for s in job.segments if s.get("speaker"))),
        "language": job.language,
        "language_probability": job.language_probability,
    }


@router.get("/job/{job_id}/search")
async def search_transcript(
    job_id: str,
    q: str = Query(..., description="Search query"),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
):
    """Search for text within a transcript."""
    job = state.jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before searching")

    if not q:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    # Audit #23: cap search query length.
    if len(q) > 200:
        raise HTTPException(status_code=400, detail="query too long")

    matches = []
    search_query = q if case_sensitive else q.lower()

    for index, segment in enumerate(job.segments):
        segment_text = segment.get("text", "")
        search_text = segment_text if case_sensitive else segment_text.lower()

        if search_query in search_text:
            matches.append({
                "index": index,
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": segment_text,
                "speaker": segment.get("speaker"),
            })

    return {
        "job_id": job_id,
        "query": q,
        "case_sensitive": case_sensitive,
        "total_matches": len(matches),
        "matches": matches,
    }

"""
Multi-modal processing API routes: PDF, PPTX, video processing.
"""

import io
import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse

from config import (
    MLX_MODELS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS_MM,
)
from models.multimodal import (
    MultiModalJob,
    VideoProcessingSettings,
    PDFProcessingSettings,
    PPTXProcessingSettings,
)
from processors.pdf_processor import PDFProcessor
from processors.pptx_processor import PPTXProcessor
from processors.video_processor import VideoProcessor
from utils.export import format_timestamp, format_srt_timestamp
from utils.export_multimodal import generate_multimodal_markdown, generate_multimodal_json
import app_state

logger = logging.getLogger(__name__)

router = APIRouter()

_max_upload_bytes = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500")) * 1024 * 1024


async def _save_upload(file: UploadFile, dest: Path):
    """Stream uploaded file to disk with size limit."""
    file_size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > _max_upload_bytes:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {_max_upload_bytes // (1024 * 1024)}MB.",
                )
            f.write(chunk)


async def _process_multimodal_job(job: MultiModalJob, file_path: Path, processor):
    """Background task for multi-modal processing."""
    try:
        await processor.run(file_path)
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        import traceback
        traceback.print_exc()


@router.post("/process/multimodal")
async def process_multimodal(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language for audio transcription"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    enable_visual_analysis: bool = Query(True, description="Analyze visual content with VLM"),
    enable_ocr: bool = Query(True, description="Extract text from images via OCR"),
):
    """Process any supported file type with auto-detection."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    file_ext = Path(file.filename).suffix.lower()

    if file_ext in SUPPORTED_VIDEO_EXTENSIONS_MM:
        source_type = "video"
    elif file_ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        if file_ext == ".pdf":
            source_type = "pdf"
        else:
            source_type = "pptx"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: {list(SUPPORTED_VIDEO_EXTENSIONS_MM.keys()) + list(SUPPORTED_DOCUMENT_EXTENSIONS.keys())}"
        )

    job = MultiModalJob(
        source_type=source_type,
        source_filename=file.filename,
        enable_diarization=enable_diarization,
        enable_visual_analysis=enable_visual_analysis,
        enable_ocr=enable_ocr,
    )
    app_state.multimodal_jobs()[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{file_ext}"

    try:
        await _save_upload(file, input_path)

        job.source_filename = str(input_path)

        if source_type == "video":
            settings = VideoProcessingSettings(
                language=language,
                enable_diarization=enable_diarization,
                enable_visual_analysis=enable_visual_analysis,
                ocr_enabled=enable_ocr,
            )
            processor = VideoProcessor(job, settings=settings)
        elif source_type == "pdf":
            settings = PDFProcessingSettings(
                describe_charts=enable_visual_analysis,
            )
            processor = PDFProcessor(job, settings=settings)
        else:
            settings = PPTXProcessingSettings(
                describe_slides=enable_visual_analysis,
            )
            processor = PPTXProcessor(job, settings=settings)

        background_tasks.add_task(_process_multimodal_job, job, input_path, processor)

        return {
            "job_id": job.job_id,
            "detected_type": source_type,
            "status": "processing",
            "filename": file.filename,
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/process/pdf")
async def process_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    extract_images: bool = Query(True, description="Extract images from PDF"),
    describe_charts: bool = Query(True, description="Describe charts/diagrams with VLM"),
    preserve_tables: bool = Query(True, description="Preserve table structure"),
):
    """Process a PDF document with text and visual extraction."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF file required")

    job = MultiModalJob(
        source_type="pdf",
        source_filename=file.filename,
    )
    app_state.multimodal_jobs()[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / "input.pdf"

    try:
        await _save_upload(file, input_path)

        job.source_filename = str(input_path)

        settings = PDFProcessingSettings(
            extract_images=extract_images,
            describe_charts=describe_charts,
            preserve_tables=preserve_tables,
        )
        processor = PDFProcessor(job, settings=settings)

        background_tasks.add_task(_process_multimodal_job, job, input_path, processor)

        return {
            "job_id": job.job_id,
            "status": "processing",
            "filename": file.filename,
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/process/pptx")
async def process_pptx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    extract_speaker_notes: bool = Query(True, description="Extract speaker notes"),
    describe_slides: bool = Query(True, description="Describe slides with VLM"),
    extract_embedded_media: bool = Query(True, description="Extract embedded audio/video"),
):
    """Process a PowerPoint presentation."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in [".pptx", ".ppt"]:
        raise HTTPException(status_code=400, detail="PowerPoint file required (.pptx or .ppt)")

    job = MultiModalJob(
        source_type="pptx",
        source_filename=file.filename,
    )
    app_state.multimodal_jobs()[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{ext}"

    try:
        await _save_upload(file, input_path)

        job.source_filename = str(input_path)

        settings = PPTXProcessingSettings(
            extract_speaker_notes=extract_speaker_notes,
            describe_slides=describe_slides,
            extract_embedded_media=extract_embedded_media,
        )
        processor = PPTXProcessor(job, settings=settings)

        background_tasks.add_task(_process_multimodal_job, job, input_path, processor)

        return {
            "job_id": job.job_id,
            "status": "processing",
            "filename": file.filename,
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/process/video")
async def process_video_multimodal(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language for transcription"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    enable_visual_analysis: bool = Query(True, description="Analyze visual content"),
    keyframe_interval: float = Query(30.0, description="Max seconds between keyframe extraction"),
    scene_detection: bool = Query(True, description="Use scene change detection"),
    model_size: str = Query("large-v3-turbo", description="Whisper model size"),
):
    """Process a video with audio transcription and visual extraction."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_VIDEO_EXTENSIONS_MM:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format. Supported: {list(SUPPORTED_VIDEO_EXTENSIONS_MM.keys())}"
        )

    if model_size not in MLX_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

    job = MultiModalJob(
        source_type="video",
        source_filename=file.filename,
        enable_diarization=enable_diarization,
        enable_visual_analysis=enable_visual_analysis,
    )
    app_state.multimodal_jobs()[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{ext}"

    try:
        await _save_upload(file, input_path)

        job.source_filename = str(input_path)

        settings = VideoProcessingSettings(
            language=language,
            enable_diarization=enable_diarization,
            enable_visual_analysis=enable_visual_analysis,
            keyframe_interval=keyframe_interval,
            scene_detection=scene_detection,
            model_size=model_size,
        )
        processor = VideoProcessor(job, settings=settings)

        background_tasks.add_task(_process_multimodal_job, job, input_path, processor)

        return {
            "job_id": job.job_id,
            "status": "processing",
            "filename": file.filename,
            "model": model_size,
        }

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/process/job/{job_id}")
async def get_multimodal_job_status(job_id: str):
    """Get the status and result of a multi-modal processing job."""
    job = app_state.multimodal_jobs().get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job.job_id,
        "source_type": job.source_type,
        "status": job.status,
        "progress": job.progress,
        "progress_message": job.progress_message,
        "duration": job.duration,
        "page_count": job.page_count,
        "slide_count": job.slide_count,
        "frames_extracted": job.frames_extracted,
        "frames_analyzed": job.frames_analyzed,
        "processing_time_seconds": job.processing_time_seconds,
    }

    if job.status == "completed":
        visual_elements_with_urls = []
        for elem in job.visual_elements:
            elem_dict = elem.model_dump()
            if elem.image_path:
                elem_dict["image_path"] = f"/process/job/{job_id}/image/{elem.element_id}"
            visual_elements_with_urls.append(elem_dict)

        response.update({
            "audio_transcript": job.audio_transcript,
            "audio_segments": [seg.model_dump() for seg in job.audio_segments],
            "visual_elements": visual_elements_with_urls,
            "document_sections": [sec.model_dump() for sec in job.document_sections],
            "document_markdown": job.document_markdown,
            "merged_timeline": [seg.model_dump() for seg in job.merged_timeline],
            "detected_language": job.detected_language,
            "speakers": job.speakers,
            "models_used": job.models_used,
        })
    elif job.status == "failed":
        response["error"] = job.error

    return response


@router.get("/process/job/{job_id}/visual-content")
async def get_visual_content(job_id: str):
    """Get extracted visual content for a multi-modal job."""
    job = app_state.multimodal_jobs().get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    visuals_with_urls = []
    for elem in job.visual_elements:
        elem_dict = elem.model_dump()
        if elem.image_path:
            elem_dict["image_path"] = f"/process/job/{job_id}/image/{elem.element_id}"
        visuals_with_urls.append(elem_dict)

    return {
        "job_id": job.job_id,
        "total_elements": len(job.visual_elements),
        "visuals": visuals_with_urls,
    }


@router.get("/process/job/{job_id}/image/{element_id}")
async def get_visual_element_image(job_id: str, element_id: str):
    """Get an image from a visual element."""
    job = app_state.multimodal_jobs().get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    element = None
    for elem in job.visual_elements:
        if elem.element_id == element_id:
            element = elem
            break

    if not element:
        raise HTTPException(status_code=404, detail="Visual element not found")

    if not element.image_path:
        raise HTTPException(status_code=404, detail="Element has no image")

    if not job.image_dir:
        raise HTTPException(status_code=403, detail="Access denied")

    image_path = Path(element.image_path).resolve()
    allowed_dir = Path(job.image_dir).resolve()

    if not image_path.is_relative_to(allowed_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    ext = image_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    media_type = media_types.get(ext, "image/png")

    return FileResponse(
        path=str(image_path),
        media_type=media_type,
        filename=f"{element_id}{ext}",
    )


@router.delete("/process/job/{job_id}")
async def delete_multimodal_job(job_id: str):
    """Delete a multi-modal processing job."""
    if job_id not in app_state.multimodal_jobs():
        raise HTTPException(status_code=404, detail="Job not found")

    job = app_state.multimodal_jobs()[job_id]

    if job.image_dir:
        image_dir_path = Path(job.image_dir)
        if image_dir_path.exists():
            try:
                shutil.rmtree(image_dir_path)
            except Exception as e:
                logger.warning(f"Failed to clean up image_dir {job.image_dir}: {e}")

    del app_state.multimodal_jobs()[job_id]
    return {"status": "deleted"}


@router.get("/process/job/{job_id}/export")
async def export_multimodal_transcript(
    job_id: str,
    format: Literal["txt", "md", "json", "srt"] = Query(..., description="Export format"),
    include_visuals: bool = Query(True, description="Include visual content in export"),
):
    """Export multi-modal transcript in various formats."""
    job = app_state.multimodal_jobs().get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Processing not completed")

    filename = f"multimodal_{job_id[:8]}"

    if format == "md":
        content = generate_multimodal_markdown(job, include_visuals)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={filename}.md"}
        )

    elif format == "json":
        content = generate_multimodal_json(job)
        return JSONResponse(
            content=content,
            headers={"Content-Disposition": f"attachment; filename={filename}.json"}
        )

    elif format == "txt":
        lines = []
        for segment in job.audio_segments:
            speaker = f"{segment.speaker}: " if segment.speaker else ""
            timestamp = format_timestamp(segment.start)
            lines.append(f"[{timestamp}] {speaker}{segment.text}")

        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}.txt"}
        )

    elif format == "srt":
        lines = []
        for i, segment in enumerate(job.audio_segments, 1):
            start = format_srt_timestamp(segment.start)
            end = format_srt_timestamp(segment.end)
            speaker_prefix = f"{segment.speaker}: " if segment.speaker else ""

            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(f"{speaker_prefix}{segment.text}")
            lines.append("")

        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={filename}.srt"}
        )

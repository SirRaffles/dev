"""
Transcription App Backend
FastAPI server with faster-whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
Features speaker diarization and multiple export formats.
Optimized for Apple Silicon (M3).
"""

import os
import io
import uuid
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Literal
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# Global model instances (loaded at startup)
whisper_model = None
diarization_pipeline = None

# In-memory job storage (for production, use Redis or database)
jobs = {}

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French",
    "auto": "Auto-detect"
}


class TranscriptionJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"  # pending, processing, completed, failed
        self.progress = 0
        self.progress_message = ""
        self.result = None
        self.error = None
        self.language = None
        self.language_probability = None
        self.segments = []
        self.speakers = []  # Speaker diarization results


class YouTubeRequest(BaseModel):
    url: str
    language: str = "auto"
    enable_diarization: bool = True


class TranscriptionSettings(BaseModel):
    beam_size: int = 10  # Higher for quality
    patience: float = 1.5  # More thorough beam search
    best_of: int = 10  # More candidates for better quality
    vad_filter: bool = True
    word_timestamps: bool = True
    language: str = "auto"  # en, fr, or auto
    enable_diarization: bool = True


def get_device_config():
    """Get optimal device configuration for the current system."""
    import platform

    system = platform.system()
    machine = platform.machine()

    # Check for Apple Silicon
    if system == "Darwin" and machine == "arm64":
        # Apple Silicon (M1/M2/M3) - use CPU with float32 for best compatibility
        # faster-whisper doesn't support MPS directly, but CPU is well optimized
        return {
            "device": "cpu",
            "compute_type": "float32",  # float32 works best on Apple Silicon
            "num_workers": 4,  # M3 has good multi-core performance
        }
    elif os.environ.get("WHISPER_DEVICE") == "cuda":
        return {
            "device": "cuda",
            "compute_type": "float16",
            "num_workers": 1,
        }
    else:
        return {
            "device": "cpu",
            "compute_type": "int8",
            "num_workers": 2,
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global whisper_model, diarization_pipeline

    device_config = get_device_config()
    print(f"System configuration: {device_config}")

    # Load Whisper model
    print("Loading Whisper model... (this may take a few minutes on first run)")
    try:
        from faster_whisper import WhisperModel

        model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3")
        print(f"Loading {model_size} model on {device_config['device']} with {device_config['compute_type']} precision...")

        whisper_model = WhisperModel(
            model_size,
            device=device_config["device"],
            compute_type=device_config["compute_type"],
            num_workers=device_config["num_workers"],
        )
        print("Whisper model loaded successfully!")
    except Exception as e:
        print(f"Warning: Could not load Whisper model: {e}")

    # Load speaker diarization pipeline
    print("Loading speaker diarization model...")
    try:
        from pyannote.audio import Pipeline
        import torch

        # Check for HuggingFace token (required for pyannote)
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

        if hf_token:
            diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )

            # Use MPS on Apple Silicon if available
            if torch.backends.mps.is_available():
                diarization_pipeline.to(torch.device("mps"))
                print("Diarization model loaded on MPS (Apple Silicon)!")
            else:
                print("Diarization model loaded on CPU!")
        else:
            print("Warning: HF_TOKEN not set. Speaker diarization requires a HuggingFace token.")
            print("Get your token at: https://huggingface.co/settings/tokens")
            print("Then accept the model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1")
    except Exception as e:
        print(f"Warning: Could not load diarization model: {e}")

    yield

    # Cleanup on shutdown
    whisper_model = None
    diarization_pipeline = None


app = FastAPI(
    title="Transcription API",
    description="High-quality audio/video transcription with speaker diarization",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract_audio(input_path: str, output_path: str) -> str:
    """Extract audio from video file using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def download_youtube_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube URL using yt-dlp."""
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", output_template,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise RuntimeError("No audio file found after download")


def run_diarization(audio_path: str) -> List[dict]:
    """Run speaker diarization on audio file."""
    global diarization_pipeline

    if diarization_pipeline is None:
        return []

    try:
        diarization = diarization_pipeline(audio_path)

        speakers = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })

        return speakers
    except Exception as e:
        print(f"Diarization error: {e}")
        return []


def assign_speakers_to_segments(segments: List[dict], speakers: List[dict]) -> List[dict]:
    """Assign speaker labels to transcription segments."""
    if not speakers:
        return segments

    for segment in segments:
        seg_mid = (segment["start"] + segment["end"]) / 2

        # Find the speaker active at the segment midpoint
        assigned_speaker = None
        for speaker_turn in speakers:
            if speaker_turn["start"] <= seg_mid <= speaker_turn["end"]:
                assigned_speaker = speaker_turn["speaker"]
                break

        segment["speaker"] = assigned_speaker or "Unknown"

    return segments


async def transcribe_audio(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Run transcription with optional speaker diarization."""
    global whisper_model, diarization_pipeline
    job = jobs.get(job_id)

    if not job:
        return

    if whisper_model is None:
        job.status = "failed"
        job.error = "Whisper model not loaded. Please restart the server."
        return

    try:
        job.status = "processing"
        job.progress = 5
        job.progress_message = "Starting transcription..."

        # Run speaker diarization first (if enabled)
        speakers = []
        if settings.enable_diarization and diarization_pipeline is not None:
            job.progress = 10
            job.progress_message = "Identifying speakers..."
            speakers = run_diarization(audio_path)
            job.speakers = speakers

        job.progress = 30
        job.progress_message = "Transcribing audio..."

        # Prepare language setting
        language = None if settings.language == "auto" else settings.language

        # Run transcription with quality-focused settings
        segments, info = whisper_model.transcribe(
            audio_path,
            beam_size=settings.beam_size,
            patience=settings.patience,
            best_of=settings.best_of,
            vad_filter=settings.vad_filter,
            word_timestamps=settings.word_timestamps,
            language=language,
            condition_on_previous_text=True,  # Better coherence
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
        )

        job.language = info.language
        job.language_probability = info.language_probability
        job.progress = 60
        job.progress_message = "Processing segments..."

        # Collect segments
        transcription_segments = []
        full_text_parts = []

        for segment in segments:
            seg_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }

            if settings.word_timestamps and hasattr(segment, 'words') and segment.words:
                seg_data["words"] = [
                    {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                    for w in segment.words
                ]

            transcription_segments.append(seg_data)
            full_text_parts.append(segment.text.strip())

        job.progress = 80
        job.progress_message = "Assigning speakers..."

        # Assign speakers to segments
        if speakers:
            transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)

        job.segments = transcription_segments
        job.result = " ".join(full_text_parts)
        job.progress = 100
        job.progress_message = "Complete!"
        job.status = "completed"

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup audio file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            parent_dir = os.path.dirname(audio_path)
            if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except Exception:
            pass


def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 100)

    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:02d}"
    return f"{mins:02d}:{secs:02d}.{ms:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def generate_txt(job: TranscriptionJob, include_timestamps: bool = True, include_speakers: bool = True) -> str:
    """Generate plain text transcript."""
    lines = []

    for segment in job.segments:
        parts = []

        if include_timestamps:
            parts.append(f"[{format_timestamp(segment['start'])}]")

        if include_speakers and segment.get("speaker"):
            parts.append(f"{segment['speaker']}:")

        parts.append(segment["text"])
        lines.append(" ".join(parts))

    return "\n".join(lines)


def generate_markdown(job: TranscriptionJob) -> str:
    """Generate Markdown transcript."""
    lines = [
        f"# Transcript",
        f"",
        f"**Language:** {SUPPORTED_LANGUAGES.get(job.language, job.language)} ({job.language_probability*100:.1f}% confidence)",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        "---",
        ""
    ]

    current_speaker = None

    for segment in job.segments:
        speaker = segment.get("speaker")

        if speaker and speaker != current_speaker:
            lines.append(f"\n### {speaker}\n")
            current_speaker = speaker

        timestamp = format_timestamp(segment["start"])
        lines.append(f"**[{timestamp}]** {segment['text']}\n")

    return "\n".join(lines)


def generate_srt(job: TranscriptionJob) -> str:
    """Generate SRT subtitle file."""
    lines = []

    for i, segment in enumerate(job.segments, 1):
        start = format_srt_timestamp(segment["start"])
        end = format_srt_timestamp(segment["end"])

        speaker_prefix = f"{segment['speaker']}: " if segment.get("speaker") else ""

        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(f"{speaker_prefix}{segment['text']}")
        lines.append("")

    return "\n".join(lines)


def generate_pdf(job: TranscriptionJob) -> bytes:
    """Generate PDF transcript."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, textColor='gray')
    speaker_style = ParagraphStyle('Speaker', parent=styles['Heading3'], fontSize=12, spaceAfter=6)
    text_style = ParagraphStyle('Text', parent=styles['Normal'], fontSize=11, leading=14, spaceAfter=12)
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor='blue')

    story = []

    # Title and metadata
    story.append(Paragraph("Transcript", title_style))
    story.append(Spacer(1, 12))

    lang_name = SUPPORTED_LANGUAGES.get(job.language, job.language)
    story.append(Paragraph(f"Language: {lang_name} ({job.language_probability*100:.1f}% confidence)", meta_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style))
    story.append(Spacer(1, 24))

    current_speaker = None

    for segment in job.segments:
        speaker = segment.get("speaker")

        if speaker and speaker != current_speaker:
            story.append(Spacer(1, 12))
            story.append(Paragraph(speaker, speaker_style))
            current_speaker = speaker

        timestamp = format_timestamp(segment["start"])
        story.append(Paragraph(f"[{timestamp}]", timestamp_style))
        story.append(Paragraph(segment["text"], text_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_docx(job: TranscriptionJob) -> bytes:
    """Generate DOCX transcript."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.add_heading("Transcript", level=1)

    # Metadata
    lang_name = SUPPORTED_LANGUAGES.get(job.language, job.language)
    meta = doc.add_paragraph()
    meta.add_run(f"Language: {lang_name} ({job.language_probability*100:.1f}% confidence)\n").italic = True
    meta.add_run(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}").italic = True

    doc.add_paragraph()  # Spacer

    current_speaker = None

    for segment in job.segments:
        speaker = segment.get("speaker")

        if speaker and speaker != current_speaker:
            doc.add_heading(speaker, level=2)
            current_speaker = speaker

        para = doc.add_paragraph()

        # Timestamp in blue
        timestamp_run = para.add_run(f"[{format_timestamp(segment['start'])}] ")
        timestamp_run.font.color.rgb = RGBColor(0, 102, 204)
        timestamp_run.font.size = Pt(9)

        # Text
        text_run = para.add_run(segment["text"])
        text_run.font.size = Pt(11)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model_loaded": whisper_model is not None,
        "diarization_available": diarization_pipeline is not None,
        "supported_languages": SUPPORTED_LANGUAGES,
        "message": "Transcription API is running"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "model_loaded": whisper_model is not None,
        "diarization_available": diarization_pipeline is not None,
        "active_jobs": len([j for j in jobs.values() if j.status == "processing"]),
        "total_jobs": len(jobs),
        "supported_languages": list(SUPPORTED_LANGUAGES.keys())
    }


@app.post("/transcribe/file")
async def transcribe_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language code: en, fr, or auto"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    beam_size: int = Query(10, description="Beam search size (higher = better quality)"),
    patience: float = Query(1.5, description="Beam search patience"),
    best_of: int = Query(10, description="Number of candidates to consider"),
):
    """Upload and transcribe an audio/video file with speaker diarization."""
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    temp_dir = tempfile.mkdtemp()
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".tmp"
    input_path = os.path.join(temp_dir, f"input{file_ext}")

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

        if file_ext in audio_extensions:
            converted_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, converted_path)
            audio_path = converted_path
        else:
            audio_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, audio_path)
            os.remove(input_path)

        settings = TranscriptionSettings(
            beam_size=beam_size,
            patience=patience,
            best_of=best_of,
            vad_filter=True,
            word_timestamps=True,
            language=language,
            enable_diarization=enable_diarization,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/youtube")
async def transcribe_youtube(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks,
    beam_size: int = Query(10, description="Beam search size"),
    patience: float = Query(1.5, description="Beam search patience"),
    best_of: int = Query(10, description="Number of candidates"),
):
    """Download and transcribe audio from a YouTube URL."""
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    if request.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    temp_dir = tempfile.mkdtemp()

    try:
        job.status = "downloading"
        job.progress_message = "Downloading audio from YouTube..."
        audio_path = download_youtube_audio(request.url, temp_dir)

        settings = TranscriptionSettings(
            beam_size=beam_size,
            patience=patience,
            best_of=best_of,
            vad_filter=True,
            word_timestamps=True,
            language=request.language,
            enable_diarization=request.enable_diarization,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        job.status = "failed"
        job.error = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status and result of a transcription job."""
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "progress_message": job.progress_message,
    }

    if job.status == "completed":
        response.update({
            "result": job.result,
            "segments": job.segments,
            "speakers": list(set(s.get("speaker") for s in job.segments if s.get("speaker"))),
            "language": job.language,
            "language_probability": job.language_probability,
        })
    elif job.status == "failed":
        response["error"] = job.error

    return response


@app.get("/job/{job_id}/export")
async def export_transcript(
    job_id: str,
    format: Literal["txt", "md", "srt", "pdf", "docx"] = Query(..., description="Export format"),
):
    """Export transcript in various formats."""
    job = jobs.get(job_id)

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


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a transcription job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs[job_id]
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

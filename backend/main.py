"""
Transcription App Backend
FastAPI server with MLX-Whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
Features speaker diarization and multiple export formats.
Optimized for Apple Silicon (M3) with GPU acceleration via Metal.
"""

import os
import io
import uuid
import tempfile
import subprocess
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Literal
from contextlib import asynccontextmanager
from datetime import datetime

# Thread pool for CPU-bound transcription tasks
transcription_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# Audio restoration
import numpy as np
import noisereduce as nr
from scipy.io import wavfile

# Global model configuration (MLX-Whisper loads model on first transcribe)
whisper_model_path = None  # HuggingFace repo path for MLX model
whisper_model_ready = False  # Flag to indicate model is configured
diarization_pipeline = None

# In-memory job storage (for production, use Redis or database)
jobs = {}
batch_jobs = {}  # Storage for batch jobs

# Supported languages (Whisper supports 99, these are the most common)
SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "pl": "Polish",
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


class BatchJob:
    def __init__(self, batch_id: str, job_ids: List[str]):
        self.batch_id = batch_id
        self.job_ids = job_ids
        self.created_at = datetime.now()
        self.total = len(job_ids)


class YouTubeRequest(BaseModel):
    url: str
    language: str = "auto"
    enable_diarization: bool = True
    enable_noise_reduction: bool = False
    translate_to_english: bool = False


class TranscriptionSettings(BaseModel):
    beam_size: int = 5  # Balanced quality/speed for CPU
    patience: float = 1.0  # Standard beam search patience
    best_of: int = 5  # Balanced candidates for CPU
    vad_filter: bool = False  # Disabled - causes empty results with some audio
    word_timestamps: bool = False  # Disabled by default for speed (can enable for precise timing)
    language: str = "auto"  # en, fr, or auto
    enable_diarization: bool = True
    num_speakers: Optional[int] = None  # Number of speakers (None = auto-detect)
    enable_noise_reduction: bool = False  # Apply noise reduction before transcription
    model_size: str = "large-v3"  # tiny, base, small, medium, large-v3
    translate_to_english: bool = False  # Translate output to English (any language → English)


# Available MLX-Whisper model sizes with descriptions
MLX_MODELS = {
    "tiny": {"path": "mlx-community/whisper-tiny", "description": "Fastest, lowest quality (~39M params)"},
    "base": {"path": "mlx-community/whisper-base", "description": "Fast, good for real-time (~74M params)"},
    "small": {"path": "mlx-community/whisper-small", "description": "Balanced speed/quality (~244M params)"},
    "medium": {"path": "mlx-community/whisper-medium", "description": "High quality, moderate speed (~769M params)"},
    "large-v3": {"path": "mlx-community/whisper-large-v3-mlx", "description": "Best quality, slowest (~1.5B params)"},
}


class SpeakerRenameRequest(BaseModel):
    speaker_mapping: dict  # {"old_name": "new_name"}


class SegmentUpdate(BaseModel):
    segments: List[dict]  # [{start, end, text, speaker}]


def get_mlx_model_path():
    """Get the MLX-Whisper model path based on environment or default."""
    # Model size mapping to MLX Community HuggingFace repos
    mlx_models = {
        "tiny": "mlx-community/whisper-tiny",
        "base": "mlx-community/whisper-base",
        "small": "mlx-community/whisper-small",
        "medium": "mlx-community/whisper-medium",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v2": "mlx-community/whisper-large-v2-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
    }

    model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3")
    return mlx_models.get(model_size, mlx_models["large-v3"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure models on startup."""
    global whisper_model_path, whisper_model_ready, diarization_pipeline

    # Configure MLX-Whisper model path
    print("Configuring MLX-Whisper for Apple Silicon GPU acceleration...")
    try:
        import mlx_whisper
        whisper_model_path = get_mlx_model_path()
        print(f"MLX-Whisper model: {whisper_model_path}")
        print("Note: Model will be downloaded on first transcription if not cached")
        whisper_model_ready = True
        print("MLX-Whisper configured successfully! (GPU-accelerated via Metal)")
    except Exception as e:
        print(f"Warning: Could not configure MLX-Whisper: {e}")

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
    whisper_model_ready = False
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


def apply_noise_reduction(audio_path: str, output_path: str) -> str:
    """Apply noise reduction to audio file using noisereduce library."""
    try:
        # Load the audio file
        sample_rate, audio_data = wavfile.read(audio_path)

        # Convert to float32 for processing
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype == np.int32:
            audio_data = audio_data.astype(np.float32) / 2147483648.0

        # Apply noise reduction with prop_decrease=0.8 for strong reduction
        reduced_noise = nr.reduce_noise(y=audio_data, sr=sample_rate, prop_decrease=0.8)

        # Convert back to int16 for saving
        reduced_noise_int16 = (reduced_noise * 32768.0).astype(np.int16)

        # Save the cleaned audio
        wavfile.write(output_path, sample_rate, reduced_noise_int16)

        return output_path
    except Exception as e:
        raise RuntimeError(f"Noise reduction failed: {e}")


def run_diarization(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization on audio file.

    Args:
        audio_path: Path to audio file
        num_speakers: Expected number of speakers (None = auto-detect)
    """
    global diarization_pipeline

    if diarization_pipeline is None:
        return []

    try:
        # Pass num_speakers hint to improve accuracy
        if num_speakers and num_speakers > 0:
            diarization = diarization_pipeline(audio_path, num_speakers=num_speakers)
        else:
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


def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker - runs in thread pool."""
    global whisper_model_path, whisper_model_ready, diarization_pipeline
    job = jobs.get(job_id)

    if not job:
        return

    if not whisper_model_ready:
        job.status = "failed"
        job.error = "MLX-Whisper not configured. Please restart the server."
        return

    try:
        import mlx_whisper

        job.status = "processing"
        job.progress = 5
        job.progress_message = "Starting transcription..."

        # Apply noise reduction (if enabled)
        if settings.enable_noise_reduction:
            job.progress = 8
            job.progress_message = "Applying noise reduction..."
            cleaned_audio_path = audio_path.replace(".wav", "_cleaned.wav")
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # Run speaker diarization first (if enabled)
        speakers = []
        if settings.enable_diarization and diarization_pipeline is not None:
            job.progress = 10
            if settings.num_speakers:
                job.progress_message = f"Identifying {settings.num_speakers} speakers..."
            else:
                job.progress_message = "Identifying speakers..."
            speakers = run_diarization(audio_path, num_speakers=settings.num_speakers)
            job.speakers = speakers

        job.progress = 20
        job.progress_message = "Transcribing with MLX-Whisper (GPU-accelerated)..."

        # Prepare language setting
        language = None if settings.language == "auto" else settings.language

        # Get the model path based on selected model size
        model_info = MLX_MODELS.get(settings.model_size, MLX_MODELS["large-v3"])
        model_path = model_info["path"]
        print(f"Using model: {settings.model_size} ({model_path})")

        # Run transcription with MLX-Whisper (uses Metal GPU on Apple Silicon)
        # Note: MLX-Whisper uses greedy decoding (beam search not yet implemented)
        # task="translate" outputs English regardless of source language
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=model_path,
            language=language,
            task="translate" if settings.translate_to_english else "transcribe",
            word_timestamps=settings.word_timestamps,
            condition_on_previous_text=True,  # Better coherence
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            verbose=False,
            fp16=True,  # Use FP16 for faster inference on Apple Silicon
        )

        # Extract language info from result
        job.language = result.get("language", "unknown")
        job.language_probability = 0.99  # MLX-Whisper doesn't provide this
        job.progress = 70
        job.progress_message = "Processing segments..."

        # Process segments from MLX-Whisper result
        transcription_segments = []
        full_text_parts = []

        for segment in result.get("segments", []):
            seg_data = {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
            }

            # Extract word timestamps if available
            if settings.word_timestamps and "words" in segment:
                seg_data["words"] = [
                    {
                        "word": w.get("word", w.get("text", "")),
                        "start": w["start"],
                        "end": w["end"],
                        "probability": w.get("probability", 1.0)
                    }
                    for w in segment["words"]
                ]

            transcription_segments.append(seg_data)
            full_text_parts.append(segment["text"].strip())

        job.progress = 90
        job.progress_message = "Finalizing..."

        # Assign speakers to segments
        if speakers:
            transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)

        job.segments = transcription_segments
        job.result = result.get("text", " ".join(full_text_parts))
        job.progress = 100
        job.progress_message = "Complete!"
        job.status = "completed"
        print(f"Transcription complete (MLX-Whisper): {len(transcription_segments)} segments")

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


async def transcribe_audio(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Run transcription in thread pool to keep event loop responsive."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        transcription_executor,
        _run_transcription_sync,
        job_id,
        audio_path,
        settings
    )


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
        "model_loaded": whisper_model_ready,
        "model_type": "MLX-Whisper (GPU-accelerated)",
        "model_path": whisper_model_path,
        "diarization_available": diarization_pipeline is not None,
        "supported_languages": SUPPORTED_LANGUAGES,
        "message": "Transcription API is running with MLX-Whisper"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "model_loaded": whisper_model_ready,
        "model_type": "MLX-Whisper",
        "model_path": whisper_model_path,
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
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    enable_noise_reduction: bool = Query(False, description="Apply noise reduction before transcription"),
    model_size: str = Query("large-v3", description="Model size: tiny, base, small, medium, large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps (slower but more precise)"),
    translate_to_english: bool = Query(False, description="Translate output to English (any language → English)"),
):
    """Upload and transcribe an audio/video file with speaker diarization."""
    if not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    if model_size not in MLX_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

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
            vad_filter=False,  # Disabled - causes empty results with some audio
            word_timestamps=word_timestamps,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=enable_noise_reduction,
            model_size=model_size,
            translate_to_english=translate_to_english,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing", "model": model_size}

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
    model_size: str = Query("large-v3", description="Model size: tiny, base, small, medium, large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
):
    """Download and transcribe audio from a YouTube URL."""
    if not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    if model_size not in MLX_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

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
            vad_filter=False,  # Disabled - causes empty results with some audio
            word_timestamps=word_timestamps,
            language=request.language,
            enable_diarization=request.enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=request.enable_noise_reduction,
            model_size=model_size,
            translate_to_english=request.translate_to_english,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing", "model": model_size}

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


@app.get("/models")
async def list_models():
    """List available transcription models with descriptions."""
    return {
        "models": [
            {"id": key, "path": val["path"], "description": val["description"]}
            for key, val in MLX_MODELS.items()
        ],
        "default": "large-v3"
    }


@app.post("/transcribe/batch")
async def transcribe_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    language: str = Query("auto", description="Language code: en, fr, or auto"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    model_size: str = Query("large-v3", description="Model size: tiny, base, small, medium, large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    translate_to_english: bool = Query(False, description="Translate output to English (any language → English)"),
):
    """Upload and transcribe multiple audio/video files in batch."""
    if not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    if model_size not in MLX_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    batch_id = str(uuid.uuid4())
    job_ids = []

    # Create individual jobs for each file
    for file in files:
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(job_id)
        jobs[job_id] = job
        job_ids.append(job_id)

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
                vad_filter=False,  # Disabled - causes empty results with some audio
                word_timestamps=word_timestamps,
                language=language,
                enable_diarization=enable_diarization,
                num_speakers=num_speakers,
                model_size=model_size,
                translate_to_english=translate_to_english,
            )

            background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        except Exception as e:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            job.status = "failed"
            job.error = str(e)

    # Create batch job to track all individual jobs
    batch = BatchJob(batch_id, job_ids)
    batch_jobs[batch_id] = batch

    return {
        "batch_id": batch_id,
        "job_ids": job_ids,
        "total": len(job_ids)
    }


@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get the status of a batch transcription job."""
    batch = batch_jobs.get(batch_id)

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Gather status of all jobs in the batch
    job_statuses = []
    completed_count = 0
    failed_count = 0
    processing_count = 0
    pending_count = 0

    for job_id in batch.job_ids:
        job = jobs.get(job_id)
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

    # Calculate overall progress
    total_progress = sum(jobs.get(jid).progress for jid in batch.job_ids if jobs.get(jid))
    overall_progress = int(total_progress / batch.total) if batch.total > 0 else 0

    # Determine overall status
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


@app.put("/job/{job_id}/speakers")
async def rename_speakers(job_id: str, request: SpeakerRenameRequest):
    """Update speaker names in a transcription job."""
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before renaming speakers")

    if not request.speaker_mapping:
        raise HTTPException(status_code=400, detail="Speaker mapping cannot be empty")

    # Update speaker names in all segments
    for segment in job.segments:
        if segment.get("speaker") and segment["speaker"] in request.speaker_mapping:
            segment["speaker"] = request.speaker_mapping[segment["speaker"]]

    # Update speaker diarization results if available
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


@app.put("/job/{job_id}/segments")
async def update_segments(job_id: str, request: SegmentUpdate):
    """Update transcript segments with inline edits."""
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before updating segments")

    if not request.segments:
        raise HTTPException(status_code=400, detail="Segments cannot be empty")

    # Validate segment structure
    required_fields = {"start", "end", "text"}
    for i, segment in enumerate(request.segments):
        if not all(field in segment for field in required_fields):
            raise HTTPException(
                status_code=400,
                detail=f"Segment {i} missing required fields. Required: {required_fields}"
            )

    # Update job segments
    job.segments = request.segments

    # Rebuild full transcript text from updated segments
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


@app.get("/job/{job_id}/search")
async def search_transcript(
    job_id: str,
    q: str = Query(..., description="Search query"),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
):
    """Search for text within a transcript."""
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before searching")

    if not q:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    # Search through segments
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

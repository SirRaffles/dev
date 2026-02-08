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
import multiprocessing
import json
import shutil
import sqlite3
import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pathlib import Path
from typing import Optional, List, Literal
from contextlib import asynccontextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# Thread pool for MLX-Whisper transcription tasks
# IMPORTANT: max_workers=1 to prevent Metal GPU race conditions on macOS 26.x
# Multiple concurrent MLX GPU operations cause MTLCommandBuffer crashes
transcription_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")

# Process pool for heavy diarization (prevents blocking main process)
# Using spawn method for macOS compatibility
multiprocessing.set_start_method('spawn', force=True)

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# Multi-modal processing imports
from models.multimodal import (
    MultiModalJob,
    VisualElement,
    VideoProcessingSettings,
    PDFProcessingSettings,
    PPTXProcessingSettings,
)
from services.model_manager import get_model_manager
from processors.pdf_processor import PDFProcessor
from processors.pptx_processor import PPTXProcessor
from processors.video_processor import VideoProcessor

# Audio restoration
import numpy as np
import noisereduce as nr
from scipy.io import wavfile

# Global model configuration (MLX-Whisper loads model on first transcribe)
whisper_model_path = None  # HuggingFace repo path for MLX model
whisper_model_ready = False  # Flag to indicate model is configured
diarization_pipeline = None

# Application startup time for uptime tracking
startup_time = None


class JobStore:
    """
    SQLite-backed job storage with in-memory cache.
    Provides persistence across backend restarts.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to user's home directory
            db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
        self.db_path = db_path
        self._cache = {}  # In-memory cache for fast access
        self._lock = threading.Lock()
        self._init_db()
        # Set restrictive permissions (owner read/write only)
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass
        self._load_active_jobs()

    def _get_connection(self):
        """Get a thread-local database connection."""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    progress_message TEXT,
                    result TEXT,
                    error TEXT,
                    language TEXT,
                    language_probability REAL,
                    segments TEXT,
                    speakers TEXT,
                    file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
            ''')
            conn.commit()
        logger.info(f"Job store initialized at {self.db_path}")

    def _load_active_jobs(self):
        """Load active (non-completed) jobs from database into cache."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM jobs WHERE status IN ('pending', 'processing')"
            )
            for row in cursor.fetchall():
                job = self._row_to_job(row)
                self._cache[job.job_id] = job
        logger.info(f"Loaded {len(self._cache)} active jobs from database")

    def _row_to_job(self, row) -> 'TranscriptionJob':
        """Convert a database row to a TranscriptionJob object."""
        job = TranscriptionJob(row[0])  # job_id
        job.status = row[1]
        job.progress = row[2] or 0
        job.progress_message = row[3] or ""
        job.result = json.loads(row[4]) if row[4] else None
        job.error = row[5]
        job.language = row[6]
        job.language_probability = row[7]
        job.segments = json.loads(row[8]) if row[8] else []
        job.speakers = json.loads(row[9]) if row[9] else []
        return job

    def _job_to_row(self, job: 'TranscriptionJob', file_path: str = None) -> tuple:
        """Convert a TranscriptionJob to database row values."""
        return (
            job.job_id,
            job.status,
            job.progress,
            job.progress_message,
            json.dumps(job.result) if job.result else None,
            job.error,
            job.language,
            job.language_probability,
            json.dumps(job.segments) if job.segments else None,
            json.dumps(job.speakers) if job.speakers else None,
            file_path,
        )

    def create(self, job: 'TranscriptionJob', file_path: str = None):
        """Create a new job in the store."""
        with self._lock:
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO jobs (job_id, status, progress, progress_message,
                                     result, error, language, language_probability,
                                     segments, speakers, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', self._job_to_row(job, file_path))
                conn.commit()

    def get(self, job_id: str) -> Optional['TranscriptionJob']:
        """Get a job by ID (from cache or database)."""
        with self._lock:
            if job_id in self._cache:
                return self._cache[job_id]

            # Try loading from database
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                if row:
                    job = self._row_to_job(row)
                    self._cache[job_id] = job
                    return job
            return None

    def update(self, job: 'TranscriptionJob'):
        """Update a job in the store."""
        with self._lock:
            self._cache[job.job_id] = job
            with self._get_connection() as conn:
                conn.execute('''
                    UPDATE jobs SET status=?, progress=?, progress_message=?,
                                   result=?, error=?, language=?, language_probability=?,
                                   segments=?, speakers=?, updated_at=CURRENT_TIMESTAMP
                    WHERE job_id=?
                ''', (
                    job.status, job.progress, job.progress_message,
                    json.dumps(job.result) if job.result else None,
                    job.error, job.language, job.language_probability,
                    json.dumps(job.segments) if job.segments else None,
                    json.dumps(job.speakers) if job.speakers else None,
                    job.job_id
                ))
                conn.commit()

    def delete(self, job_id: str):
        """Delete a job from the store."""
        with self._lock:
            self._cache.pop(job_id, None)
            with self._get_connection() as conn:
                conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
                conn.commit()

    def get_all(self) -> dict:
        """Get all cached jobs (for API responses)."""
        return dict(self._cache)

    def get_active_count(self) -> int:
        """Get count of active (processing) jobs."""
        return len([j for j in self._cache.values() if j.status == "processing"])

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists in store."""
        return self.get(job_id) is not None

    def __len__(self) -> int:
        """Return number of cached jobs."""
        return len(self._cache)

    def __setitem__(self, job_id: str, job: 'TranscriptionJob'):
        """Set a job (create or update)."""
        if job_id in self._cache:
            self.update(job)
        else:
            self.create(job)

    def __getitem__(self, job_id: str) -> 'TranscriptionJob':
        """Get a job by ID, raises KeyError if not found."""
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def __delitem__(self, job_id: str):
        """Delete a job by ID."""
        self.delete(job_id)

    def values(self):
        """Return cached job values (for compatibility)."""
        return self._cache.values()

    def keys(self):
        """Return cached job keys (for compatibility)."""
        return self._cache.keys()

    def items(self):
        """Return cached job items (for compatibility)."""
        return self._cache.items()


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


# Initialize job stores (must be after TranscriptionJob class definition)
job_store = JobStore()
batch_jobs = {}  # Batch jobs remain in-memory (short-lived)
multimodal_jobs = {}  # Multi-modal jobs remain in-memory for now

# Legacy compatibility: jobs dict now backed by JobStore
jobs = job_store


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
    model_size: str = "large-v3-turbo"  # tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3
    translate_to_english: bool = False  # Translate output to English (any language → English)
    engine: str = "whisper"  # "whisper" | "voxtral-api"
    context_terms: Optional[List[str]] = None  # Voxtral context biasing (up to 100 terms)


# Available MLX-Whisper model sizes with descriptions
MLX_MODELS = {
    "tiny": {"path": "mlx-community/whisper-tiny", "description": "Fastest, lowest quality (~39M params)"},
    "base": {"path": "mlx-community/whisper-base", "description": "Fast, good for real-time (~74M params)"},
    "small": {"path": "mlx-community/whisper-small", "description": "Balanced speed/quality (~244M params)"},
    "medium": {"path": "mlx-community/whisper-medium", "description": "High quality, moderate speed (~769M params)"},
    "large-v3": {"path": "mlx-community/whisper-large-v3-mlx", "description": "Best quality, slowest (~1.5B params)"},
    "large-v3-turbo": {"path": "mlx-community/whisper-large-v3-turbo", "description": "6x faster, near-best quality (~809M params)"},
    "distil-large-v3": {"path": "mlx-community/distil-whisper-large-v3", "description": "5x faster, fewer hallucinations (~756M params)"},
}

# English-only optimized model (Parakeet MLX - 60x real-time on Apple Silicon)
# Parakeet uses CTC/RNN-T architecture and is optimized for English
PARAKEET_MODEL = {
    "path": "mlx-community/parakeet-tdt-0.6b-v2",  # Default Parakeet model
    "description": "60x real-time, English only (~600M params)",
    "language": "en",
}

# Voxtral cloud transcription models (Mistral API)
VOXTRAL_MODELS = {
    "voxtral-mini": {
        "api_id": "voxtral-mini-latest",
        "description": "Cloud: Best accuracy, built-in diarization ($0.003/min)",
        "engine": "voxtral-api",
    },
}
_voxtral_available = False
_voxtral_service = None

# Check if Parakeet is available and has correct API
_parakeet_available = False
_parakeet_model = None  # Cached model instance
try:
    import parakeet_mlx
    # Verify the module has the expected from_pretrained function
    if hasattr(parakeet_mlx, 'from_pretrained'):
        _parakeet_available = True
except ImportError:
    pass


def select_optimal_model(language: str, model_size: str, speed_priority: bool = False) -> str:
    """
    Select the optimal model based on language and speed preference.

    For English with speed_priority=True, use Parakeet MLX (60x real-time).
    For other cases, use the user-selected model or default to large-v3-turbo.
    """
    # If speed priority is enabled and language is English, suggest Parakeet
    # (Fall back to large-v3-turbo if Parakeet isn't available)
    if speed_priority and language == "en":
        if _parakeet_available:
            return "parakeet"
        # Fall back to large-v3-turbo for speed
        return "large-v3-turbo"

    # Use the user-selected model
    return model_size


def transcribe_with_parakeet(audio_path: str) -> dict:
    """
    Transcribe audio using Parakeet MLX (60x real-time on Apple Silicon).

    Parakeet is English-only but significantly faster than Whisper.

    Args:
        audio_path: Path to audio file (wav, mp3, etc.)

    Returns:
        Dict with 'text' and 'segments' keys
    """
    global _parakeet_model
    import parakeet_mlx

    print("Transcribing with Parakeet MLX (60x real-time)...")

    # Load model (cached for reuse)
    if _parakeet_model is None:
        print(f"Loading Parakeet model: {PARAKEET_MODEL['path']}")
        _parakeet_model = parakeet_mlx.from_pretrained(PARAKEET_MODEL["path"])
        print("Parakeet model loaded successfully")

    # Transcribe using the model's transcribe method
    result = _parakeet_model.transcribe(audio_path)

    # Convert AlignedResult to our segment format
    segments = []
    all_text_parts = []

    # AlignedResult has a 'tokens' attribute containing aligned tokens/sentences
    if hasattr(result, 'tokens') and result.tokens:
        for token in result.tokens:
            # Each token may have start, end, and text-like attributes
            text_part = ""
            start_time = 0.0
            end_time = 0.0

            # Handle different token structures
            if hasattr(token, 'text'):
                text_part = str(token.text).strip()
            elif hasattr(token, '__str__'):
                text_part = str(token).strip()

            if hasattr(token, 'start'):
                start_time = float(token.start)
            if hasattr(token, 'end'):
                end_time = float(token.end)

            if text_part:
                all_text_parts.append(text_part)
                segments.append({
                    "start": start_time,
                    "end": end_time,
                    "text": text_part,
                })
    elif hasattr(result, '__str__'):
        # Fallback: convert result to string
        text = str(result).strip()
        all_text_parts.append(text)
        segments.append({"start": 0, "end": 0, "text": text})

    full_text = " ".join(all_text_parts)

    return {
        "text": full_text,
        "segments": segments,
        "language": "en",  # Parakeet is English-only
    }


def transcribe_with_voxtral(audio_path: str, settings: TranscriptionSettings) -> dict:
    """
    Transcribe audio using Voxtral Mini Transcribe V2 (Mistral API).

    Voxtral provides ~4% WER accuracy with built-in speaker diarization.
    No separate pyannote step needed — speakers are returned inline.

    Args:
        audio_path: Path to audio file (wav, mp3, flac, etc.)
        settings: Transcription settings with language, diarization, etc.

    Returns:
        Dict with 'text', 'segments', 'language', and 'speakers' keys
    """
    if not _voxtral_service:
        raise RuntimeError("Voxtral API not configured. Set MISTRAL_API_KEY environment variable.")

    print("Transcribing with Voxtral Mini (cloud API)...")

    language = None if settings.language == "auto" else settings.language

    result = _voxtral_service.transcribe(
        audio_path=audio_path,
        language=language or "auto",
        enable_diarization=settings.enable_diarization,
        word_timestamps=settings.word_timestamps,
        context_terms=settings.context_terms,
    )

    return result


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
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "distil-large-v3": "mlx-community/distil-whisper-large-v3",
    }

    model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
    return mlx_models.get(model_size, mlx_models["large-v3-turbo"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure models on startup."""
    global whisper_model_path, whisper_model_ready, diarization_pipeline, startup_time

    # Record startup time for health monitoring
    startup_time = time.time()

    # Configure MLX-Whisper model path
    print("Configuring MLX-Whisper for Apple Silicon GPU acceleration...")
    try:
        import mlx_whisper
        import mlx.core as mx

        # Test Metal GPU availability and stability
        metal_ok = False
        try:
            if mx.metal.is_available():
                # Run a quick GPU test to check for Metal stability
                test_array = mx.ones((10, 10))
                mx.eval(test_array @ test_array)  # Force GPU execution
                print(f"Metal GPU: OK (device: {mx.default_device()})")
                metal_ok = True
            else:
                print("Metal GPU: Not available, using CPU")
                mx.set_default_device(mx.cpu)
        except Exception as gpu_err:
            print(f"Metal GPU: Unstable ({gpu_err}), falling back to CPU")
            mx.set_default_device(mx.cpu)

        whisper_model_path = get_mlx_model_path()
        print(f"MLX-Whisper model: {whisper_model_path}")
        print("Note: Model will be downloaded on first transcription if not cached")
        whisper_model_ready = True
        device_mode = "GPU-accelerated via Metal" if metal_ok else "CPU mode"
        print(f"MLX-Whisper configured successfully! ({device_mode})")
    except Exception as e:
        print(f"Warning: Could not configure MLX-Whisper: {e}")

    # Check for diarization availability (model loaded on-demand in subprocess)
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if hf_token:
        print("Speaker diarization: Available (HF_TOKEN set)")
        print("Note: Diarization model loads in subprocess to keep server responsive")
        # Mark as available for health check
        diarization_pipeline = True  # Placeholder to indicate availability
    else:
        print("Warning: HF_TOKEN not set. Speaker diarization requires a HuggingFace token.")
        print("Get your token at: https://huggingface.co/settings/tokens")
        print("Then accept the model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1")

    # Check for Voxtral API availability
    global _voxtral_available, _voxtral_service
    mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    if mistral_api_key:
        from services.voxtral_service import VoxtralService
        _voxtral_service = VoxtralService(mistral_api_key)
        _voxtral_available = True
        print("Voxtral API: Available (MISTRAL_API_KEY set)")
    else:
        print("Voxtral API: Not configured (set MISTRAL_API_KEY for cloud transcription)")

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
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key authentication middleware
# Set API_KEY env var to enable; leave unset to disable auth (local dev)
_api_key = os.environ.get("API_KEY")

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _api_key:
            return await call_next(request)
        # Allow health endpoint without auth
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)
        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)
        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if key != _api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)

if _api_key:
    app.add_middleware(APIKeyMiddleware)
    logger.info("API key authentication enabled")


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


def _is_valid_youtube_url(url: str) -> bool:
    """Validate that the URL is a legitimate YouTube URL."""
    import re
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?',
        r'^https?://(www\.)?youtube\.com/shorts/',
        r'^https?://(www\.)?youtube\.com/embed/',
        r'^https?://youtu\.be/',
        r'^https?://music\.youtube\.com/watch\?',
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def download_youtube_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube URL using yt-dlp."""
    if not _is_valid_youtube_url(url):
        raise ValueError("Invalid URL. Only YouTube URLs are accepted.")

    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-exec",
        "--no-batch",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", output_template,
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)  # 10 min timeout
    except subprocess.TimeoutExpired:
        raise RuntimeError("YouTube download timed out after 10 minutes")

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise RuntimeError("No audio file found after download")


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    import re

    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_youtube_transcript(video_id: str, language: str = "auto") -> Optional[dict]:
    """Try to get existing YouTube transcript (instant, no download needed).

    Returns transcript in our segment format, or None if no transcript available.
    This is much faster than downloading and transcribing with Whisper.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )

        try:
            api = YouTubeTranscriptApi()

            # Get available transcripts
            transcript_list = api.list(video_id)

            # Try to get transcript in requested language
            transcript = None
            detected_language = None

            if language != "auto":
                # Try exact language match first
                try:
                    transcript = transcript_list.find_transcript([language]).fetch()
                    detected_language = language
                except NoTranscriptFound:
                    # Try translated version
                    try:
                        for t in transcript_list:
                            if t.is_translatable:
                                transcript = t.translate(language).fetch()
                                detected_language = language
                                break
                    except Exception:
                        pass

            # If no specific language or not found, get any available transcript
            if transcript is None:
                for t in transcript_list:
                    transcript = t.fetch()
                    detected_language = t.language_code
                    break

            if transcript is None:
                # Last resort: just fetch default transcript
                transcript = api.fetch(video_id)
                detected_language = "auto"

            if transcript is None:
                return None

            # Convert to our segment format (handle both dict and object formats)
            segments = []
            for item in transcript:
                # Handle FetchedTranscriptSnippet objects
                if hasattr(item, 'text'):
                    start = float(item.start)
                    duration = float(item.duration) if hasattr(item, 'duration') else 0
                    text = item.text.strip()
                else:
                    # Handle dict format
                    start = float(item.get("start", 0))
                    duration = float(item.get("duration", 0))
                    text = item.get("text", "").strip()

                segments.append({
                    "start": start,
                    "end": start + duration,
                    "text": text,
                })

            # Build full text
            full_text = " ".join(seg["text"] for seg in segments)

            return {
                "segments": segments,
                "text": full_text,
                "language": detected_language,
                "source": "youtube_captions",  # Mark as from YouTube captions
            }

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
            return None

    except ImportError:
        print("Warning: youtube-transcript-api not installed")
        return None
    except Exception as e:
        print(f"Error getting YouTube transcript: {e}")
        return None


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


def _diarization_worker(audio_path: str, num_speakers: Optional[int], output_file: str, hf_token: str):
    """Subprocess worker for diarization. Runs in separate process to avoid blocking main server."""
    try:
        import os
        os.environ["HF_TOKEN"] = hf_token

        from pyannote.audio import Pipeline
        import torch

        # Load pipeline in subprocess
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )

        # Use MPS if available
        if torch.backends.mps.is_available():
            pipeline.to(torch.device("mps"))

        # Run diarization
        if num_speakers and num_speakers > 0:
            diarization = pipeline(audio_path, num_speakers=num_speakers)
        else:
            diarization = pipeline(audio_path)

        speakers = []

        # Handle pyannote 4.x API
        if hasattr(diarization, 'speaker_diarization'):
            annotation = diarization.speaker_diarization
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                speakers.append({
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "speaker": str(speaker)
                })
        else:
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers.append({
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "speaker": str(speaker)
                })

        # Write results to file
        with open(output_file, 'w') as f:
            json.dump({"status": "success", "speakers": speakers}, f)

    except Exception as e:
        import traceback
        with open(output_file, 'w') as f:
            json.dump({"status": "error", "error": str(e), "traceback": traceback.format_exc()}, f)


def run_diarization_subprocess(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization in a separate subprocess to prevent blocking.

    This keeps the FastAPI server responsive during long diarization jobs.
    Uses polling with sleep to allow other threads to run.
    """
    import time

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""

    if not hf_token:
        print("Warning: HF_TOKEN not set, diarization will fail")
        return []

    # Create temp file for results
    _tf = tempfile.NamedTemporaryFile(suffix="_diarization.json", delete=False)
    output_file = _tf.name
    _tf.close()

    try:
        # Start diarization in subprocess
        process = multiprocessing.Process(
            target=_diarization_worker,
            args=(audio_path, num_speakers, output_file, hf_token)
        )
        process.start()

        # Poll for completion instead of blocking join
        # This allows the thread pool to be more responsive
        poll_interval = 5  # Check every 5 seconds
        max_wait = 7200  # 2 hour timeout
        elapsed = 0

        while process.is_alive() and elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            if elapsed % 60 == 0:  # Log every minute
                print(f"Diarization in progress... ({elapsed}s elapsed)")

        if process.is_alive():
            print(f"Diarization timeout after {max_wait}s, terminating...")
            process.terminate()
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
            return []

        # Wait for process cleanup
        process.join(timeout=5)

        # Read results
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                result = json.load(f)

            if result.get("status") == "success":
                speakers = result.get("speakers", [])
                print(f"Diarization complete: {len(speakers)} speaker segments found")
                return speakers
            else:
                print(f"Diarization subprocess error: {result.get('error')}")
                if result.get('traceback'):
                    print(result.get('traceback'))
                return []
        else:
            print("Diarization subprocess did not produce output")
            return []

    except Exception as e:
        print(f"Diarization subprocess failed: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        # Cleanup
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except OSError:
                pass


def run_diarization(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization on audio file.

    Uses subprocess for long audio files to prevent blocking the server.

    Args:
        audio_path: Path to audio file
        num_speakers: Expected number of speakers (None = auto-detect)
    """
    # Always use subprocess for diarization to prevent server blocking
    return run_diarization_subprocess(audio_path, num_speakers)


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

    # Check engine/model availability
    use_voxtral = settings.engine == "voxtral-api"
    use_parakeet = settings.model_size == "parakeet" and not use_voxtral

    if use_voxtral:
        if not _voxtral_available:
            job.status = "failed"
            job.error = "Voxtral API not configured. Set MISTRAL_API_KEY environment variable."
            return
    elif use_parakeet:
        if not _parakeet_available:
            job.status = "failed"
            job.error = "Parakeet MLX not installed. Install with: pip install parakeet-mlx"
            return
    elif not whisper_model_ready:
        job.status = "failed"
        job.error = "MLX-Whisper not configured. Please restart the server."
        return

    try:
        job.status = "processing"
        job.progress = 5
        job.progress_message = "Starting transcription..."

        # Apply noise reduction (if enabled)
        if settings.enable_noise_reduction:
            job.progress = 8
            job.progress_message = "Applying noise reduction..."
            cleaned_audio_path = audio_path.replace(".wav", "_cleaned.wav")
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # === VOXTRAL API ENGINE ===
        if use_voxtral:
            job.progress = 15
            job.progress_message = "Transcribing with Voxtral (cloud API)..."

            result = transcribe_with_voxtral(audio_path, settings)

            job.language = result.get("language", "unknown")
            job.language_probability = 0.99

            transcription_segments = result.get("segments", [])
            full_text = result.get("text", "")

            # Voxtral returns speakers inline — extract unique speaker list
            voxtral_speakers = result.get("speakers", [])
            if voxtral_speakers:
                job.speakers = [{"speaker": s} for s in voxtral_speakers]

        else:
            # === LOCAL ENGINES (Whisper / Parakeet) ===
            # Run speaker diarization first (if enabled)
            # Diarization runs in a separate subprocess to keep server responsive
            speakers = []
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
            if settings.enable_diarization and hf_token:
                job.progress = 10
                if settings.num_speakers:
                    job.progress_message = f"Identifying {settings.num_speakers} speakers..."
                else:
                    job.progress_message = "Identifying speakers..."
                speakers = run_diarization(audio_path, num_speakers=settings.num_speakers)
                job.speakers = speakers

            job.progress = 20

            # Use Parakeet or MLX-Whisper based on model selection
            if use_parakeet:
                job.progress_message = "Transcribing with Parakeet MLX (60x real-time)..."
                print("Using Parakeet MLX for English transcription")

                result = transcribe_with_parakeet(audio_path)

                # Extract results
                job.language = "en"
                job.language_probability = 0.99

                transcription_segments = result.get("segments", [])
                full_text = result.get("text", "")

            else:
                # Use MLX-Whisper
                import mlx_whisper

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

                full_text = result.get("text", " ".join(full_text_parts))

            # Assign speakers to segments (local engines only — Voxtral does this inline)
            if speakers:
                transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)

        job.progress = 70
        job.progress_message = "Processing segments..."

        job.progress = 90
        job.progress_message = "Finalizing..."

        job.segments = transcription_segments
        job.result = full_text
        job.progress = 100
        job.progress_message = "Complete!"
        job.status = "completed"
        jobs.update(job)
        model_name = "Voxtral" if use_voxtral else ("Parakeet MLX" if use_parakeet else "MLX-Whisper")
        logger.info(f"Transcription complete ({model_name}): {len(transcription_segments)} segments")

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        jobs.update(job)
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
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "supported_languages": SUPPORTED_LANGUAGES,
        "message": "Transcription API is running with MLX-Whisper"
    }


@app.get("/health")
async def health():
    """
    Detailed health check with model functionality verification.
    Returns degraded status if model isn't ready to process.
    """
    # Determine overall status
    is_ready = whisper_model_ready
    status = "healthy" if is_ready else "degraded"

    # Calculate uptime
    uptime_seconds = None
    if startup_time:
        uptime_seconds = int(time.time() - startup_time)

    # Test Metal GPU availability (non-blocking quick check)
    gpu_available = False
    try:
        import mlx.core as mx
        gpu_available = mx.metal.is_available()
    except Exception:
        pass

    return {
        "status": status,
        "model_loaded": whisper_model_ready,
        "model_functional": is_ready,  # Can we actually process transcriptions?
        "model_type": "MLX-Whisper",
        "model_path": whisper_model_path,
        "gpu_available": gpu_available,
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "voxtral_available": _voxtral_available,
        "engines": {
            "whisper": {"available": whisper_model_ready, "type": "local"},
            "voxtral-api": {"available": _voxtral_available, "type": "cloud"},
        },
        "active_jobs": job_store.get_active_count(),
        "total_jobs": len(job_store),
        "uptime_seconds": uptime_seconds,
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
    model_size: str = Query("large-v3-turbo", description="Model size: tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps (slower but more precise)"),
    translate_to_english: bool = Query(False, description="Translate output to English (any language → English)"),
    speed_priority: bool = Query(False, description="Optimize for speed (uses fastest model for language)"),
    engine: str = Query("whisper", description="Transcription engine: whisper (local) or voxtral-api (cloud)"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms for Voxtral (up to 100)"),
):
    """Upload and transcribe an audio/video file with speaker diarization."""
    # Validate engine
    if engine == "voxtral-api":
        if not _voxtral_available:
            raise HTTPException(status_code=503, detail="Voxtral API not configured. Set MISTRAL_API_KEY environment variable.")
    elif engine != "whisper":
        raise HTTPException(status_code=400, detail=f"Invalid engine. Use: whisper or voxtral-api")

    if engine == "whisper" and not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    # Select optimal model based on language and speed preference (whisper engine only)
    effective_model = model_size
    if engine == "whisper":
        effective_model = select_optimal_model(language, model_size, speed_priority)
        if effective_model not in MLX_MODELS and effective_model != "parakeet":
            raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    # Validate file extension
    ALLOWED_EXTENSIONS = {
        ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac",  # audio
        ".mp4", ".mkv", ".avi", ".webm", ".mov",           # video
    }
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".tmp"
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, f"input{file_ext}")

    # Max upload size: 500MB (configurable via MAX_UPLOAD_SIZE_MB env var)
    max_size = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500")) * 1024 * 1024

    try:
        # Stream file to disk in chunks to avoid loading entire file into memory
        file_size = 0
        with open(input_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                if file_size > max_size:
                    f.close()
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB."
                    )
                f.write(chunk)

        audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

        if file_ext in audio_extensions:
            converted_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, converted_path)
            audio_path = converted_path
        else:
            audio_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, audio_path)
            os.remove(input_path)

        # Parse context terms from comma-separated string
        parsed_context_terms = None
        if context_terms:
            parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

        settings = TranscriptionSettings(
            vad_filter=False,  # Disabled - causes empty results with some audio
            word_timestamps=word_timestamps,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=enable_noise_reduction,
            model_size=effective_model,
            translate_to_english=translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing", "model": effective_model, "engine": engine}

    except Exception as e:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/transcribe/youtube")
async def transcribe_youtube(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks,
    model_size: str = Query("large-v3-turbo", description="Model size: tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    use_captions: bool = Query(True, description="Try YouTube captions first (instant, if available)"),
    speed_priority: bool = Query(False, description="Optimize for speed (uses fastest model for language)"),
    engine: str = Query("whisper", description="Transcription engine: whisper (local) or voxtral-api (cloud)"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms for Voxtral (up to 100)"),
):
    """Download and transcribe audio from a YouTube URL.

    If use_captions=True (default), tries to get existing YouTube captions first.
    This is instant and doesn't require downloading. Falls back to Whisper if
    no captions are available.
    """
    # Validate engine
    if engine == "voxtral-api":
        if not _voxtral_available:
            raise HTTPException(status_code=503, detail="Voxtral API not configured. Set MISTRAL_API_KEY environment variable.")
    elif engine != "whisper":
        raise HTTPException(status_code=400, detail=f"Invalid engine. Use: whisper or voxtral-api")

    if engine == "whisper" and not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    # Select optimal model based on language and speed preference (whisper engine only)
    effective_model = model_size
    if engine == "whisper":
        effective_model = select_optimal_model(request.language, model_size, speed_priority)
        if effective_model not in MLX_MODELS and effective_model != "parakeet":
            raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

    if request.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    # Extract video ID from URL
    video_id = extract_video_id(request.url)

    # Try YouTube captions first (instant, no download needed)
    if use_captions and video_id:
        job.status = "processing"
        job.progress_message = "Checking for YouTube captions..."

        transcript = get_youtube_transcript(video_id, request.language)

        if transcript:
            # Success! Return completed job immediately
            job.status = "completed"
            job.progress = 100
            job.progress_message = "Complete (YouTube captions)"
            job.segments = transcript["segments"]
            job.result = transcript["text"]
            job.language = transcript["language"]
            job.language_probability = 1.0  # Captions are definitive

            return {
                "job_id": job_id,
                "status": "completed",
                "source": "youtube_captions",
                "language": transcript["language"],
                "segment_count": len(transcript["segments"]),
            }

    # Fall back to download + Whisper transcription
    temp_dir = tempfile.mkdtemp()

    try:
        job.status = "downloading"
        job.progress_message = "Downloading audio from YouTube..."

        # Run download in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        audio_path = await loop.run_in_executor(
            transcription_executor,
            download_youtube_audio,
            request.url,
            temp_dir
        )

        # Parse context terms from comma-separated string
        parsed_context_terms = None
        if context_terms:
            parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

        settings = TranscriptionSettings(
            vad_filter=False,  # Disabled - causes empty results with some audio
            word_timestamps=word_timestamps,
            language=request.language,
            enable_diarization=request.enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=request.enable_noise_reduction,
            model_size=effective_model,
            translate_to_english=request.translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
        )

        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing", "source": engine, "model": model_size, "engine": engine}

    except Exception as e:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        job.status = "failed"
        job.error = str(e)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
    models = [
        {"id": key, "path": val["path"], "description": val["description"], "engine": "whisper"}
        for key, val in MLX_MODELS.items()
    ]

    # Add Parakeet if available
    if _parakeet_available:
        models.append({
            "id": "parakeet",
            "path": PARAKEET_MODEL["path"],
            "description": PARAKEET_MODEL["description"],
            "language": "en",  # English only
            "engine": "whisper",
        })

    # Add Voxtral models if available
    if _voxtral_available:
        for key, val in VOXTRAL_MODELS.items():
            models.append({
                "id": key,
                "api_id": val["api_id"],
                "description": val["description"],
                "engine": val["engine"],
            })

    return {
        "models": models,
        "default": "large-v3-turbo",
        "parakeet_available": _parakeet_available,
        "voxtral_available": _voxtral_available,
    }


@app.post("/transcribe/batch")
async def transcribe_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    language: str = Query("auto", description="Language code: en, fr, or auto"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    model_size: str = Query("large-v3-turbo", description="Model size: tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    translate_to_english: bool = Query(False, description="Translate output to English (any language → English)"),
    speed_priority: bool = Query(False, description="Optimize for speed (uses fastest model for language)"),
    engine: str = Query("whisper", description="Transcription engine: whisper (local) or voxtral-api (cloud)"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms for Voxtral (up to 100)"),
):
    """Upload and transcribe multiple audio/video files in batch."""
    # Validate engine
    if engine == "voxtral-api":
        if not _voxtral_available:
            raise HTTPException(status_code=503, detail="Voxtral API not configured. Set MISTRAL_API_KEY environment variable.")
    elif engine != "whisper":
        raise HTTPException(status_code=400, detail=f"Invalid engine. Use: whisper or voxtral-api")

    if engine == "whisper" and not whisper_model_ready:
        raise HTTPException(status_code=503, detail="MLX-Whisper not configured")

    # Select optimal model based on language and speed preference (whisper engine only)
    effective_model = model_size
    if engine == "whisper":
        effective_model = select_optimal_model(language, model_size, speed_priority)
        if effective_model not in MLX_MODELS and effective_model != "parakeet":
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

            # Parse context terms from comma-separated string
            parsed_context_terms = None
            if context_terms:
                parsed_context_terms = [t.strip() for t in context_terms.split(",") if t.strip()][:100]

            settings = TranscriptionSettings(
                vad_filter=False,  # Disabled - causes empty results with some audio
                word_timestamps=word_timestamps,
                language=language,
                enable_diarization=enable_diarization,
                num_speakers=num_speakers,
                model_size=effective_model,
                translate_to_english=translate_to_english,
                engine=engine,
                context_terms=parsed_context_terms,
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


# =============================================================================
# MULTI-MODAL PROCESSING ENDPOINTS
# =============================================================================

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf": "PDF document",
    ".pptx": "PowerPoint presentation",
    ".ppt": "PowerPoint (legacy)",
}

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4": "MP4 video",
    ".mov": "QuickTime video",
    ".mkv": "Matroska video",
    ".avi": "AVI video",
    ".webm": "WebM video",
}


async def _process_multimodal_job(job: MultiModalJob, file_path: Path, processor):
    """Background task for multi-modal processing."""
    try:
        await processor.run(file_path)
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        import traceback
        traceback.print_exc()


@app.post("/process/multimodal")
async def process_multimodal(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language for audio transcription"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    enable_visual_analysis: bool = Query(True, description="Analyze visual content with VLM"),
    enable_ocr: bool = Query(True, description="Extract text from images via OCR"),
):
    """
    Process any supported file type with auto-detection.

    Supports:
    - Videos: MP4, MOV, MKV, AVI, WEBM (audio + visual extraction)
    - PDFs: Text, images, tables extraction
    - PowerPoints: Slides, notes, embedded media
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    file_ext = Path(file.filename).suffix.lower()

    # Determine file type and create appropriate job
    if file_ext in SUPPORTED_VIDEO_EXTENSIONS:
        source_type = "video"
    elif file_ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        if file_ext == ".pdf":
            source_type = "pdf"
        else:
            source_type = "pptx"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: {list(SUPPORTED_VIDEO_EXTENSIONS.keys()) + list(SUPPORTED_DOCUMENT_EXTENSIONS.keys())}"
        )

    # Create job
    job = MultiModalJob(
        source_type=source_type,
        source_filename=file.filename,
        enable_diarization=enable_diarization,
        enable_visual_analysis=enable_visual_analysis,
        enable_ocr=enable_ocr,
    )
    multimodal_jobs[job.job_id] = job

    # Save uploaded file
    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{file_ext}"

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        # Update job with actual path
        job.source_filename = str(input_path)

        # Create appropriate processor
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
        else:  # pptx
            settings = PPTXProcessingSettings(
                describe_slides=enable_visual_analysis,
            )
            processor = PPTXProcessor(job, settings=settings)

        # Run in background
        background_tasks.add_task(_process_multimodal_job, job, input_path, processor)

        return {
            "job_id": job.job_id,
            "detected_type": source_type,
            "status": "processing",
            "filename": file.filename,
        }

    except Exception as e:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/process/pdf")
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
    multimodal_jobs[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / "input.pdf"

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

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
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/process/pptx")
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
    multimodal_jobs[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{ext}"

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

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
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/process/video")
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
    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format. Supported: {list(SUPPORTED_VIDEO_EXTENSIONS.keys())}"
        )

    if model_size not in MLX_MODELS:
        raise HTTPException(status_code=400, detail=f"Invalid model size. Use: {list(MLX_MODELS.keys())}")

    job = MultiModalJob(
        source_type="video",
        source_filename=file.filename,
        enable_diarization=enable_diarization,
        enable_visual_analysis=enable_visual_analysis,
    )
    multimodal_jobs[job.job_id] = job

    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input{ext}"

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

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
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Internal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/process/job/{job_id}")
async def get_multimodal_job_status(job_id: str):
    """Get the status and result of a multi-modal processing job."""
    job = multimodal_jobs.get(job_id)

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
        # Transform visual elements to include API URLs for images
        visual_elements_with_urls = []
        for elem in job.visual_elements:
            elem_dict = elem.model_dump()
            # Replace filesystem path with API URL
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


@app.get("/process/job/{job_id}/visual-content")
async def get_visual_content(job_id: str):
    """Get extracted visual content for a multi-modal job."""
    job = multimodal_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Transform visual elements to include API URLs for images
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


@app.get("/process/job/{job_id}/image/{element_id}")
async def get_visual_element_image(job_id: str, element_id: str):
    """Get an image from a visual element."""
    job = multimodal_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find the visual element by ID
    element = None
    for elem in job.visual_elements:
        if elem.element_id == element_id:
            element = elem
            break

    if not element:
        raise HTTPException(status_code=404, detail="Visual element not found")

    if not element.image_path:
        raise HTTPException(status_code=404, detail="Element has no image")

    image_path = Path(element.image_path).resolve()

    # Path traversal protection: ensure image is within the job's image directory
    if job.image_dir:
        allowed_dir = Path(job.image_dir).resolve()
        if not str(image_path).startswith(str(allowed_dir)):
            raise HTTPException(status_code=403, detail="Access denied")

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    # Determine media type from extension
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


@app.delete("/process/job/{job_id}")
async def delete_multimodal_job(job_id: str):
    """Delete a multi-modal processing job."""
    if job_id not in multimodal_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = multimodal_jobs[job_id]

    # Clean up image directory if it exists
    if job.image_dir:
        image_dir_path = Path(job.image_dir)
        if image_dir_path.exists():
            try:
                shutil.rmtree(image_dir_path)
            except Exception as e:
                logger.warning(f"Failed to clean up image_dir {job.image_dir}: {e}")

    del multimodal_jobs[job_id]
    return {"status": "deleted"}


def generate_multimodal_markdown(job: MultiModalJob, include_visuals: bool = True) -> str:
    """Generate enhanced markdown with visual content."""
    lines = [
        f"# Multi-Modal Transcript",
        f"",
        f"**Source:** {Path(job.source_filename).name if job.source_filename else 'Unknown'}",
        f"**Type:** {job.source_type}",
    ]

    if job.duration:
        mins = int(job.duration // 60)
        secs = int(job.duration % 60)
        lines.append(f"**Duration:** {mins}:{secs:02d}")

    if job.detected_language:
        lines.append(f"**Language:** {SUPPORTED_LANGUAGES.get(job.detected_language, job.detected_language)}")

    if job.speakers:
        lines.append(f"**Speakers:** {', '.join(job.speakers)}")

    lines.extend(["", "---", ""])

    # Document content (for PDF/PPTX)
    if job.document_markdown:
        lines.append("## Document Content")
        lines.append("")
        lines.append(job.document_markdown)
        lines.append("")

    # Timeline with visual references (for video)
    if job.merged_timeline:
        lines.append("## Timeline")
        lines.append("")

        current_visual = None

        for segment in job.merged_timeline:
            # Show visual change
            if include_visuals and segment.visual and segment.visual != current_visual:
                current_visual = segment.visual
                lines.append("---")
                lines.append(f"### Visual: {segment.visual.type.value.title()}")
                lines.append(f"*Timestamp: {format_timestamp(segment.visual.timestamp or 0)}*")
                lines.append("")

                if segment.visual.text_content:
                    lines.append("```")
                    lines.append(segment.visual.text_content)
                    lines.append("```")
                    lines.append("")

                if segment.visual.description:
                    lines.append(f"> {segment.visual.description}")
                    lines.append("")

            # Show audio segment
            if segment.audio:
                speaker = segment.audio.speaker or ""
                timestamp = format_timestamp(segment.audio.start)
                lines.append(f"**[{timestamp}] {speaker}:** {segment.audio.text}")
                lines.append("")

    # Audio-only segments (fallback)
    elif job.audio_segments:
        lines.append("## Transcript")
        lines.append("")

        current_speaker = None
        for segment in job.audio_segments:
            speaker = segment.speaker

            if speaker and speaker != current_speaker:
                lines.append(f"\n### {speaker}\n")
                current_speaker = speaker

            timestamp = format_timestamp(segment.start)
            lines.append(f"**[{timestamp}]** {segment.text}")
            lines.append("")

    # Visual elements list (for documents)
    if include_visuals and job.visual_elements and job.source_type in ["pdf", "pptx"]:
        lines.append("")
        lines.append("## Visual Elements")
        lines.append("")

        for i, elem in enumerate(job.visual_elements, 1):
            location = ""
            if elem.page:
                location = f"Page {elem.page}"
            elif elem.slide:
                location = f"Slide {elem.slide}"

            lines.append(f"### {i}. {elem.type.value.title()} ({location})")

            if elem.description:
                lines.append(f"> {elem.description}")
                lines.append("")

            if elem.text_content:
                lines.append("**Extracted Text:**")
                lines.append("```")
                lines.append(elem.text_content[:500] + ("..." if len(elem.text_content) > 500 else ""))
                lines.append("```")
                lines.append("")

    # Metadata footer
    lines.extend([
        "",
        "---",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*Models used: {', '.join(job.models_used)}*" if job.models_used else "",
        f"*Processing time: {job.processing_time_seconds:.1f}s*" if job.processing_time_seconds else "",
    ])

    return "\n".join(lines)


def generate_multimodal_json(job: MultiModalJob) -> dict:
    """Generate structured JSON export."""
    return {
        "version": "2.0.0",
        "job_id": job.job_id,
        "source": {
            "filename": Path(job.source_filename).name if job.source_filename else None,
            "type": job.source_type,
            "duration": job.duration,
            "page_count": job.page_count,
            "slide_count": job.slide_count,
        },
        "processing": {
            "models_used": job.models_used,
            "processing_time_seconds": job.processing_time_seconds,
            "frames_extracted": job.frames_extracted,
            "frames_analyzed": job.frames_analyzed,
        },
        "audio": {
            "language": job.detected_language,
            "language_probability": job.language_probability,
            "speakers": job.speakers,
            "transcript": job.audio_transcript,
            "segments": [seg.model_dump() for seg in job.audio_segments],
        },
        "visual": {
            "elements": [elem.model_dump() for elem in job.visual_elements],
        },
        "document": {
            "markdown": job.document_markdown,
            "sections": [sec.model_dump() for sec in job.document_sections],
        },
        "multimodal": {
            "merged_timeline": [seg.model_dump() for seg in job.merged_timeline],
        },
    }


@app.get("/process/job/{job_id}/export")
async def export_multimodal_transcript(
    job_id: str,
    format: Literal["txt", "md", "json", "srt"] = Query(..., description="Export format"),
    include_visuals: bool = Query(True, description="Include visual content in export"),
):
    """Export multi-modal transcript in various formats."""
    job = multimodal_jobs.get(job_id)

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
        # Plain text - audio transcript only
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
        # SRT format - audio only
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


@app.get("/models/status")
async def get_models_status():
    """Get current model loading status and memory usage."""
    model_manager = get_model_manager()
    return model_manager.get_status()


@app.post("/models/preload")
async def preload_models(
    models: List[str] = Query(..., description="Models to preload: whisper, vision, diarization"),
):
    """Preload models for faster processing."""
    model_manager = get_model_manager()
    results = {}

    for model_name in models:
        try:
            if model_name == "whisper":
                success = await model_manager.load_whisper()
            elif model_name == "vision":
                success = await model_manager.load_vision()
            elif model_name == "diarization":
                success = await model_manager.load_diarization()
            else:
                results[model_name] = {"success": False, "error": "Unknown model"}
                continue

            results[model_name] = {"success": success}
        except Exception as e:
            results[model_name] = {"success": False, "error": str(e)}

    return {"results": results, "status": model_manager.get_status()}


@app.post("/models/unload")
async def unload_models(
    models: List[str] = Query(..., description="Models to unload: vision, diarization"),
):
    """Unload models to free memory."""
    from services.model_manager import ModelName

    model_manager = get_model_manager()
    results = {}

    model_mapping = {
        "whisper": ModelName.WHISPER,
        "vision": ModelName.VISION,
        "diarization": ModelName.DIARIZATION,
    }

    for model_name in models:
        if model_name not in model_mapping:
            results[model_name] = {"success": False, "error": "Unknown model"}
            continue

        try:
            success = model_manager.unload_model(model_mapping[model_name])
            results[model_name] = {"success": success}
        except Exception as e:
            results[model_name] = {"success": False, "error": str(e)}

    return {"results": results, "status": model_manager.get_status()}


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8000)

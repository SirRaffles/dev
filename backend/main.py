"""
Transcription App Backend
FastAPI server with faster-whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
"""

import os
import uuid
import asyncio
import tempfile
import subprocess
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

# Global model instance (loaded at startup)
whisper_model = None

# In-memory job storage (for production, use Redis or database)
jobs = {}


class TranscriptionJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"  # pending, processing, completed, failed
        self.progress = 0
        self.result = None
        self.error = None
        self.language = None
        self.language_probability = None
        self.segments = []


class YouTubeRequest(BaseModel):
    url: str


class TranscriptionSettings(BaseModel):
    beam_size: int = 5
    patience: float = 1.0
    best_of: int = 5
    vad_filter: bool = True
    word_timestamps: bool = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load Whisper model on startup."""
    global whisper_model
    print("Loading Whisper model... (this may take a few minutes on first run)")

    try:
        from faster_whisper import WhisperModel

        # Use large-v3 for best quality
        # For CPU: device="cpu", compute_type="int8"
        # For GPU: device="cuda", compute_type="float16"
        device = os.environ.get("WHISPER_DEVICE", "cpu")
        compute_type = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
        model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3")

        print(f"Loading {model_size} model on {device} with {compute_type} precision...")
        whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("Model loaded successfully!")
    except Exception as e:
        print(f"Warning: Could not load Whisper model: {e}")
        print("Transcription will not be available until the model is loaded.")

    yield

    # Cleanup on shutdown
    whisper_model = None


app = FastAPI(
    title="Transcription API",
    description="High-quality audio/video transcription using Whisper Large-V3",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # High-quality WAV
        "-ar", "16000",  # 16 kHz (Whisper's expected sample rate)
        "-ac", "1",  # Mono
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
        "-x",  # Extract audio
        "--audio-format", "wav",
        "--audio-quality", "0",  # Best quality
        "--postprocessor-args", "-ar 16000 -ac 1",  # 16kHz mono for Whisper
        "-o", output_template,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    # Find the downloaded file
    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise RuntimeError("No audio file found after download")


async def transcribe_audio(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Run transcription in background."""
    global whisper_model
    job = jobs.get(job_id)

    if not job:
        return

    if whisper_model is None:
        job.status = "failed"
        job.error = "Whisper model not loaded. Please restart the server."
        return

    try:
        job.status = "processing"
        job.progress = 10

        # Run transcription
        segments, info = whisper_model.transcribe(
            audio_path,
            beam_size=settings.beam_size,
            patience=settings.patience,
            best_of=settings.best_of,
            vad_filter=settings.vad_filter,
            word_timestamps=settings.word_timestamps,
        )

        job.language = info.language
        job.language_probability = info.language_probability
        job.progress = 30

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

        job.segments = transcription_segments
        job.result = " ".join(full_text_parts)
        job.progress = 100
        job.status = "completed"

    except Exception as e:
        job.status = "failed"
        job.error = str(e)

    finally:
        # Cleanup audio file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            # Remove parent temp directory if empty
            parent_dir = os.path.dirname(audio_path)
            if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except Exception:
            pass


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model_loaded": whisper_model is not None,
        "message": "Transcription API is running"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "model_loaded": whisper_model is not None,
        "active_jobs": len([j for j in jobs.values() if j.status == "processing"]),
        "total_jobs": len(jobs)
    }


@app.post("/transcribe/file")
async def transcribe_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    beam_size: int = 5,
    patience: float = 1.0,
    best_of: int = 5,
    vad_filter: bool = True,
    word_timestamps: bool = True,
):
    """
    Upload and transcribe an audio/video file.

    Supported formats: mp3, wav, mp4, mkv, avi, webm, m4a, flac, ogg, etc.
    """
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Create job
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    # Save uploaded file
    temp_dir = tempfile.mkdtemp()
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".tmp"
    input_path = os.path.join(temp_dir, f"input{file_ext}")

    try:
        contents = await file.read()
        with open(input_path, "wb") as f:
            f.write(contents)

        # Extract audio if video file
        audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

        if file_ext in audio_extensions:
            audio_path = input_path
            # Still convert to 16kHz mono WAV for consistency
            converted_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, converted_path)
            audio_path = converted_path
        else:
            # Video file - extract audio
            audio_path = os.path.join(temp_dir, "audio.wav")
            extract_audio(input_path, audio_path)
            # Remove original file
            os.remove(input_path)

        settings = TranscriptionSettings(
            beam_size=beam_size,
            patience=patience,
            best_of=best_of,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )

        # Start background transcription
        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        # Cleanup on error
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
    beam_size: int = 5,
    patience: float = 1.0,
    best_of: int = 5,
    vad_filter: bool = True,
    word_timestamps: bool = True,
):
    """
    Download and transcribe audio from a YouTube URL.
    """
    if whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper model not loaded")

    # Create job
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    jobs[job_id] = job

    temp_dir = tempfile.mkdtemp()

    try:
        # Download audio from YouTube
        job.status = "downloading"
        audio_path = download_youtube_audio(request.url, temp_dir)

        settings = TranscriptionSettings(
            beam_size=beam_size,
            patience=patience,
            best_of=best_of,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )

        # Start background transcription
        background_tasks.add_task(transcribe_audio, job_id, audio_path, settings)

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        # Cleanup on error
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
    }

    if job.status == "completed":
        response.update({
            "result": job.result,
            "segments": job.segments,
            "language": job.language,
            "language_probability": job.language_probability,
        })
    elif job.status == "failed":
        response["error"] = job.error

    return response


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

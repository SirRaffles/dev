"""
Transcription App Backend
FastAPI server with MLX-Whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
Features speaker diarization and multiple export formats.
Optimized for Apple Silicon (M3) with GPU acceleration via Metal.
"""

import asyncio
import os
import json
import time
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

# Structured JSON log formatter for production log aggregation.
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

# Configure logging with rotation
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
_log_format_mode = os.environ.get("LOG_FORMAT", "text").lower()
_log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_log_datefmt = "%Y-%m-%d %H:%M:%S"
_log_file = os.environ.get("LOG_FILE", os.path.expanduser("~/Library/Logs/whisper/backend.log"))

# Ensure log directory exists with restrictive permissions
_log_dir = os.path.dirname(_log_file)
if _log_dir:
    os.makedirs(_log_dir, exist_ok=True)
    try:
        os.chmod(_log_dir, 0o700)
    except OSError:
        pass

_text_formatter = logging.Formatter(_log_format, datefmt=_log_datefmt)
_json_formatter = JsonFormatter(datefmt=_log_datefmt)

# Rotating file handler: 10MB per file, keep 3 backups
_file_handler = RotatingFileHandler(_log_file, maxBytes=10 * 1024 * 1024, backupCount=3)
_file_handler.setFormatter(_json_formatter if _log_format_mode == "json" else _text_formatter)

# Console handler (for interactive/development use) — always plain text
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_text_formatter)

logging.basicConfig(level=_log_level, handlers=[_file_handler, _console_handler])

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import state
from migrations import run_migrations
from rate_limit import check_rate_limit
from services.transcription import get_mlx_model_path
from routes.transcription import router as transcription_router
from routes.multimodal import router as multimodal_router
from routes.models_api import router as models_router
from routes.refinement import router as refinement_router
from routes.speakers import router as speakers_router
from routes.calls import router as calls_router
from routes.contexts import router as contexts_router
from routes.jpr import router as jpr_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure models on startup."""
    # Run DB migrations before anything else touches the database
    _db_path = os.path.expanduser("~/.whisper_transcription_jobs.db")
    run_migrations(_db_path)

    # Record startup time for health monitoring
    state.startup_time = time.time()

    # Configure MLX-Whisper model path
    logger.info("Configuring MLX-Whisper for Apple Silicon GPU acceleration...")
    try:
        import mlx_whisper
        import mlx.core as mx

        metal_ok = False
        try:
            if mx.metal.is_available():
                test_array = mx.ones((10, 10))
                mx.eval(test_array @ test_array)
                logger.info("Metal GPU: OK (device: %s)", mx.default_device())
                metal_ok = True
            else:
                logger.info("Metal GPU: Not available, using CPU")
                mx.set_default_device(mx.cpu)
        except Exception as gpu_err:
            logger.warning("Metal GPU: Unstable (%s), falling back to CPU", gpu_err)
            mx.set_default_device(mx.cpu)

        state.whisper_model_path = get_mlx_model_path()
        logger.info("MLX-Whisper model: %s", state.whisper_model_path)
        logger.info("Note: Model will be downloaded on first transcription if not cached")
        state.whisper_model_ready = True
        device_mode = "GPU-accelerated via Metal" if metal_ok else "CPU mode"
        logger.info("MLX-Whisper configured successfully! (%s)", device_mode)
    except Exception as e:
        logger.warning("Could not configure MLX-Whisper: %s", e)

    # Check for diarization availability
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if hf_token:
        logger.info("Speaker diarization: Available (HF_TOKEN set)")
        logger.info("Note: Diarization model loads in subprocess to keep server responsive")
        state.diarization_pipeline = True
    else:
        logger.warning("HF_TOKEN not set. Speaker diarization requires a HuggingFace token for rate limits.")
        logger.warning("Get a (read-only) token at: https://huggingface.co/settings/tokens")
        logger.warning("Model: https://huggingface.co/pyannote/speaker-diarization-community-1 (no terms acceptance required)")

    # Check for refinement availability
    if state.refinement_available:
        logger.info("Transcript refinement: Available (claude CLI found)")
    else:
        logger.info("Transcript refinement: Not available (claude CLI not found)")

    # Check for Voxtral Local availability (via mlx-audio)
    if state._voxtral_local_available:
        logger.info("Voxtral Local: Available (mlx-audio installed)")
        logger.info("Note: Voxtral model will be downloaded on first use if not cached")
    else:
        logger.info("Voxtral Local: Not available (install mlx-audio for local Voxtral transcription)")

    # Initialize iCloud Drive directory structure for call intelligence
    from config import ICLOUD_BASE_PATH
    for subdir in ("speakers", "speakers/_unknown", "contexts", "calls"):
        (ICLOUD_BASE_PATH / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("iCloud Drive data directory: %s", ICLOUD_BASE_PATH)

    # Check for Voxtral API availability
    mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    if mistral_api_key:
        from services.voxtral_service import VoxtralService
        state._voxtral_service = VoxtralService(mistral_api_key)
        state._voxtral_available = True
        logger.info("Voxtral API: Available (MISTRAL_API_KEY set)")
    else:
        logger.info("Voxtral API: Not configured (set MISTRAL_API_KEY for cloud transcription)")

    # Opportunistic prune of old jobs at startup (audit #14)
    try:
        state.job_store.prune_completed()
    except Exception as prune_err:
        logger.warning("Startup prune_completed failed: %s", prune_err)

    yield

    # Cleanup on shutdown
    state.whisper_model_ready = False
    state.diarization_pipeline = None
    try:
        state.job_store.prune_completed()
    except Exception as prune_err:
        logger.warning("Shutdown prune_completed failed: %s", prune_err)
    try:
        # Audit #20: shut down the module-level transcription executor.
        state.transcription_executor.shutdown(wait=False)
    except Exception as shutdown_err:
        logger.warning("Transcription executor shutdown failed: %s", shutdown_err)


app = FastAPI(
    title="Transcription API",
    description="High-quality audio/video transcription with speaker diarization",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
_cors_origins = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if o.strip()]

# Audit #1/#18: wildcard origins are incompatible with allow_credentials=True.
if "*" in _cors_origins:
    raise ValueError("CORS_ORIGINS cannot contain * when allow_credentials=True")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Security headers middleware
_enforce_https = os.environ.get("ENFORCE_HTTPS", "").lower() == "true"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if _enforce_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Audit #1: no shared-secret auth; backend binds to 127.0.0.1 and sits behind Tailscale.

# Include route modules with rate limiting applied at router level (audit #2)
_rate_dep = [Depends(check_rate_limit)]
app.include_router(models_router, dependencies=_rate_dep)
app.include_router(transcription_router, dependencies=_rate_dep)
app.include_router(multimodal_router, dependencies=_rate_dep)
app.include_router(refinement_router, dependencies=_rate_dep)
app.include_router(speakers_router, dependencies=_rate_dep)
app.include_router(calls_router, dependencies=_rate_dep)
app.include_router(contexts_router, dependencies=_rate_dep)
app.include_router(jpr_router, dependencies=_rate_dep)


# Serve frontend build from static/ when running in single-container mode.
# Must be mounted AFTER all API routers so /api paths take priority.
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static-frontend")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8000)

"""
Transcription App Backend
FastAPI server with MLX-Whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
Features speaker diarization and multiple export formats.
Optimized for Apple Silicon (M3) with GPU acceleration via Metal.
"""

import os
import hmac
import time
import logging
import multiprocessing
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

# Configure logging with rotation
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
_log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_log_datefmt = "%Y-%m-%d %H:%M:%S"
_log_file = os.environ.get("LOG_FILE", os.path.expanduser("~/.whisper-backend.log"))

_formatter = logging.Formatter(_log_format, datefmt=_log_datefmt)

# Rotating file handler: 10MB per file, keep 3 backups
_file_handler = RotatingFileHandler(_log_file, maxBytes=10 * 1024 * 1024, backupCount=3)
_file_handler.setFormatter(_formatter)

# Console handler (for interactive/development use)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logging.basicConfig(level=_log_level, handlers=[_file_handler, _console_handler])

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Must be set before any multiprocessing usage
multiprocessing.set_start_method('spawn', force=True)

import state
from services.transcription import get_mlx_model_path
from routes.transcription import router as transcription_router
from routes.multimodal import router as multimodal_router
from routes.models_api import router as models_router
from routes.refinement import router as refinement_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure models on startup."""
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
        logger.warning("HF_TOKEN not set. Speaker diarization requires a HuggingFace token.")
        logger.warning("Get your token at: https://huggingface.co/settings/tokens")
        logger.warning("Then accept the model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1")

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

    # Check for Voxtral API availability
    mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    if mistral_api_key:
        from services.voxtral_service import VoxtralService
        state._voxtral_service = VoxtralService(mistral_api_key)
        state._voxtral_available = True
        logger.info("Voxtral API: Available (MISTRAL_API_KEY set)")
    else:
        logger.info("Voxtral API: Not configured (set MISTRAL_API_KEY for cloud transcription)")

    yield

    # Cleanup on shutdown
    state.whisper_model_ready = False
    state.diarization_pipeline = None


app = FastAPI(
    title="Transcription API",
    description="High-quality audio/video transcription with speaker diarization",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# API key authentication middleware
_api_key = os.environ.get("API_KEY")


def _check_api_key(request: Request) -> bool:
    """Check if the request carries a valid API key (timing-safe)."""
    key = request.headers.get("X-API-Key") or ""
    if not _api_key:
        return True
    return hmac.compare_digest(key, _api_key)


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        # Allow /health, /docs, /openapi.json through without blocking,
        # but /health will check auth itself to decide response detail level.
        if request.url.path in ("/health", "/", "/docs", "/openapi.json"):
            request.state.authenticated = _check_api_key(request)
            return await call_next(request)
        # Exempt localhost requests (local frontend on same machine)
        client_ip = request.client.host if request.client else ""
        if client_ip in ("127.0.0.1", "::1"):
            request.state.authenticated = True
            return await call_next(request)
        if not _check_api_key(request):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        request.state.authenticated = True
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)
if _api_key:
    logger.info("API key authentication enabled")
else:
    logger.warning("WARNING: API_KEY not set — all endpoints are unauthenticated. Set API_KEY env var for production use.")

# Include route modules
app.include_router(models_router)
app.include_router(transcription_router)
app.include_router(multimodal_router)
app.include_router(refinement_router)


# Serve frontend build from static/ when running in single-container mode.
# Must be mounted AFTER all API routers so /api paths take priority.
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static-frontend")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8000)

"""
Transcription App Backend
FastAPI server with MLX-Whisper for high-quality transcription.
Supports local file uploads (audio/video) and YouTube URLs.
Features speaker diarization and multiple export formats.
Optimized for Apple Silicon (M3) with GPU acceleration via Metal.
"""

import os
import time
import logging
import multiprocessing
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Must be set before any multiprocessing usage
multiprocessing.set_start_method('spawn', force=True)

import state
from services.transcription import get_mlx_model_path
from routes.transcription import router as transcription_router
from routes.multimodal import router as multimodal_router
from routes.models_api import router as models_router

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

# API key authentication middleware
_api_key = os.environ.get("API_KEY")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _api_key:
            return await call_next(request)
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if key != _api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


if _api_key:
    app.add_middleware(APIKeyMiddleware)
    logger.info("API key authentication enabled")

# Include route modules
app.include_router(models_router)
app.include_router(transcription_router)
app.include_router(multimodal_router)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=8000)

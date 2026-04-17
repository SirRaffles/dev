"""
Model management API routes: list, preload, unload, status.
"""

import os
import time
from typing import List

from fastapi import APIRouter, HTTPException, Query, Request

from config import SUPPORTED_LANGUAGES, MLX_MODELS, PARAKEET_MODELS, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS
from services.model_manager import get_model_manager, ModelName
import state

router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model_loaded": state.whisper_model_ready,
        "model_type": "MLX-Whisper (GPU-accelerated)",
        "model_path": state.whisper_model_path,
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "supported_languages": SUPPORTED_LANGUAGES,
        "message": "Transcription API is running with MLX-Whisper"
    }


@router.get("/health")
async def health(request: Request):
    """Detailed health check with model functionality verification.

    Returns minimal info when unauthenticated (API_KEY is set but not provided).
    Full details are returned when authenticated or when API_KEY is not configured.
    """
    is_ready = state.whisper_model_ready
    status = "healthy" if is_ready else "degraded"

    # If API_KEY is configured but request is unauthenticated, return minimal info
    authenticated = getattr(request.state, "authenticated", True)
    if not authenticated:
        return {"status": status}

    uptime_seconds = None
    if state.startup_time:
        uptime_seconds = int(time.time() - state.startup_time)

    gpu_available = False
    try:
        import mlx.core as mx
        gpu_available = mx.metal.is_available()
    except Exception:
        pass

    return {
        "status": status,
        "model_loaded": state.whisper_model_ready,
        "model_functional": is_ready,
        "model_type": "MLX-Whisper",
        "model_path": state.whisper_model_path,
        "gpu_available": gpu_available,
        "diarization_available": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
        "voxtral_available": state._voxtral_available,
        "engines": {
            "whisper": {"available": state.whisper_model_ready, "type": "local"},
            "voxtral-local": {"available": state._voxtral_local_available, "type": "local"},
            "voxtral-api": {"available": state._voxtral_available, "type": "cloud"},
        },
        "refinement_available": state.refinement_available,
        "active_jobs": state.job_store.get_active_count(),
        "total_jobs": len(state.job_store),
        "uptime_seconds": uptime_seconds,
        "supported_languages": list(SUPPORTED_LANGUAGES.keys())
    }


@router.get("/models")
async def list_models():
    """List available transcription models with descriptions."""
    models = [
        {"id": key, "path": val["path"], "description": val["description"], "engine": "whisper"}
        for key, val in MLX_MODELS.items()
    ]

    if state._parakeet_available:
        # Surface every Parakeet variant. "parakeet" is kept as a legacy alias
        # for the English v2 model (handled by the transcription service).
        for key, val in PARAKEET_MODELS.items():
            models.append({
                "id": key,
                "path": val["path"],
                "description": val["description"],
                "language": val.get("language", "en"),
                "supported_languages": val.get("supported_languages", [val.get("language", "en")]),
                "engine": "whisper",
            })

    if state._voxtral_local_available:
        for key, val in VOXTRAL_LOCAL_MODELS.items():
            models.append({
                "id": key,
                "path": val["path"],
                "description": val["description"],
                "engine": "voxtral-local",
            })

    if state._voxtral_available:
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
        "parakeet_available": state._parakeet_available,
        "voxtral_local_available": state._voxtral_local_available,
        "voxtral_available": state._voxtral_available,
        "engine_capabilities": {
            "whisper": {
                "context_bias": False,
                "timestamps": True,
                "word_timestamps": True,
                "diarization": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
                "translation": True,
                "noise_reduction": True,
                "two_pass": False,
            },
            "voxtral-local": {
                "context_bias": False,
                "timestamps": True,
                "word_timestamps": False,
                "diarization": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
                "translation": False,
                "noise_reduction": True,
                "two_pass": False,
            },
            "voxtral-api": {
                "context_bias": True,
                "timestamps": True,
                "word_timestamps": True,
                "diarization": True,
                "translation": False,
                "noise_reduction": True,
                "two_pass": True,
            },
        },
    }


@router.get("/models/status")
async def get_models_status():
    """Get current model loading status and memory usage."""
    model_manager = get_model_manager()
    return model_manager.get_status()


@router.post("/models/preload")
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


@router.post("/models/unload")
async def unload_models(
    models: List[str] = Query(..., description="Models to unload: vision, diarization"),
):
    """Unload models to free memory."""
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

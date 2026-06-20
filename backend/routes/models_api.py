"""
Model management API routes: list, preload, unload, status.
"""

import os
import time
from typing import List

from fastapi import APIRouter, HTTPException, Query, Request

from config import (
    SUPPORTED_LANGUAGES,
    MLX_MODELS,
    PARAKEET_MODELS,
    REFINEMENT_MODEL,
    REFINEMENT_PROVIDER,
    VISION_MODEL_LABEL,
    VISION_MODEL_PATH,
)
from services.model_manager import get_model_manager, ModelName
import state
import app_state

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
    _startup_time = app_state.startup_time()
    if _startup_time:
        uptime_seconds = int(time.time() - _startup_time)

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
        "engines": {
            "whisper": {"available": state.whisper_model_ready, "type": "local"},
        },
        "refinement_available": app_state.refinement_available(),
        "refinement_provider": REFINEMENT_PROVIDER,
        "refinement_model": REFINEMENT_MODEL if app_state.refinement_available() else None,
        "vision_model_path": VISION_MODEL_PATH,
        "vision_model_label": VISION_MODEL_LABEL,
        "active_jobs": app_state.jobs().get_active_count(),
        "total_jobs": len(app_state.jobs()),
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

    return {
        "models": models,
        "default": "large-v3-turbo",
        "parakeet_available": state._parakeet_available,
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
        },
        "vision_model_path": VISION_MODEL_PATH,
        "vision_model_label": VISION_MODEL_LABEL,
        "refinement_provider": REFINEMENT_PROVIDER,
        "refinement_model": REFINEMENT_MODEL,
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
